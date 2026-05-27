"""
TradeFlow AI — XGBoost Rejection Predictor (Phase 3, Step 3.2)

PRD §13 — Trains on submission_outcomes table.
Features: CRS pillars, HS confidence, company historical rate, duty value.
Target: binary (0=accepted, 1=rejected).

The model artifact is stored in MinIO at:
  models/rejection_predictor/model_v{version}.joblib
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import joblib
import numpy as np
import structlog
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

from ..config import settings

log = structlog.get_logger()

FEATURE_NAMES = [
    "doc_quality_score",
    "completeness_score",
    "consistency_score",
    "historical_rate",
    "hs_confidence",
    "cif_value_usd",
    "package_count",
    "gross_weight_kg",
]

MODEL_LOCAL_PATH = Path("/tmp/rejection_predictor.joblib")


class RejectionPredictor:
    """
    XGBoost binary classifier for customs declaration rejection prediction.
    """

    def __init__(self) -> None:
        self._pipeline: Pipeline | None = None
        self._model_version: str = "0"

    def _load_from_minio(self) -> bool:
        """Download latest model from MinIO."""
        try:
            import boto3
            from botocore.client import Config

            s3 = boto3.client(
                "s3",
                endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                config=Config(signature_version="s3v4"),
                region_name="us-east-1",
            )
            # List versions, pick latest
            response = s3.list_objects_v2(
                Bucket=settings.STORAGE_BUCKET_NAME,
                Prefix="models/rejection_predictor/",
            )
            objects = sorted(
                response.get("Contents", []),
                key=lambda x: x["LastModified"],
                reverse=True,
            )
            if not objects:
                log.warning("No model found in MinIO — using heuristic fallback")
                return False

            latest_key = objects[0]["Key"]
            self._model_version = latest_key.split("model_v")[1].replace(".joblib", "")

            buf = io.BytesIO()
            s3.download_fileobj(settings.STORAGE_BUCKET_NAME, latest_key, buf)
            buf.seek(0)
            self._pipeline = joblib.load(buf)
            log.info("Model loaded from MinIO", version=self._model_version, key=latest_key)
            return True
        except Exception as exc:
            log.error("Failed to load model from MinIO", error=str(exc))
            return False

    def load(self) -> None:
        """Load model — try MinIO, fallback to local cache."""
        if not self._load_from_minio():
            if MODEL_LOCAL_PATH.exists():
                self._pipeline = joblib.load(MODEL_LOCAL_PATH)
                log.info("Model loaded from local cache")
            else:
                log.warning("No model available — predictions will use heuristic")

    def predict_proba(self, features: dict) -> float:
        """
        Returns probability of rejection (0.0–1.0).
        If model is not loaded, falls back to heuristic.
        """
        feature_vec = np.array(
            [[features.get(f, 0.0) for f in FEATURE_NAMES]], dtype=np.float32
        )

        if self._pipeline is not None:
            try:
                prob = float(self._pipeline.predict_proba(feature_vec)[0][1])
                log.debug("XGBoost prediction", prob=prob, version=self._model_version)
                return prob
            except Exception as exc:
                log.error("XGBoost inference error", error=str(exc))

        # Heuristic fallback: 1 - average of available scores
        known = [v for k, v in features.items() if "score" in k or "confidence" in k]
        return round(1.0 - (sum(known) / len(known)), 4) if known else 0.5

    def train_and_upload(
        self,
        X: np.ndarray,
        y: np.ndarray,
        version: str,
    ) -> None:
        """
        Train a new XGBoost model and upload to MinIO.
        Called by the Celery `retrain_predictor` task when ≥100 new samples.
        """
        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("xgb", xgb.XGBClassifier(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                use_label_encoder=False,
                eval_metric="logloss",
                random_state=42,
            )),
        ])
        pipeline.fit(X, y)

        buf = io.BytesIO()
        joblib.dump(pipeline, buf)
        buf.seek(0)

        # Upload to MinIO
        try:
            import boto3
            from botocore.client import Config

            s3 = boto3.client(
                "s3",
                endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                config=Config(signature_version="s3v4"),
                region_name="us-east-1",
            )
            key = f"models/rejection_predictor/model_v{version}.joblib"
            s3.upload_fileobj(buf, settings.STORAGE_BUCKET_NAME, key)
            log.info("New model uploaded to MinIO", version=version, key=key)
            self._pipeline = pipeline
            self._model_version = version
        except Exception as exc:
            log.error("Failed to upload model to MinIO", error=str(exc))
            raise


# ── Singleton — loaded once per Celery worker startup ─────────────────────────
rejection_predictor = RejectionPredictor()
