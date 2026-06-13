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
from pathlib import Path
from typing import Any

import structlog

try:
    import numpy as np
except Exception:  # pragma: no cover - optional in lightweight test environments
    np = None

try:
    import joblib
except Exception:  # pragma: no cover - optional in lightweight test environments
    joblib = None

try:
    from sklearn.pipeline import Pipeline
except Exception:  # pragma: no cover - optional in lightweight test environments
    Pipeline = object

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
        self._auc: float | None = None
        self._load_attempted = False

    def _load_from_minio(self) -> bool:
        """Download latest model from MinIO."""
        if joblib is None:
            log.warning("joblib is not installed; using heuristic predictor fallback")
            return False

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
        self._load_attempted = True
        if not self._load_from_minio():
            if MODEL_LOCAL_PATH.exists():
                if joblib is None:
                    log.warning("Local model exists but joblib is unavailable")
                    return
                self._pipeline = joblib.load(MODEL_LOCAL_PATH)
                log.info("Model loaded from local cache")
            else:
                log.warning("No model available — predictions will use heuristic")

    def predict_proba(self, features: dict) -> float:
        """
        Returns probability of rejection (0.0–1.0).
        If model is not loaded, falls back to heuristic.
        """
        if np is not None:
            feature_vec = np.array(
                [[features.get(f, 0.0) for f in FEATURE_NAMES]], dtype=np.float32
            )
        else:
            feature_vec = [[features.get(f, 0.0) for f in FEATURE_NAMES]]

        if self._pipeline is None and not self._load_attempted:
            self.load()

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
        X: Any,
        y: Any,
        version: str,
        *,
        current_auc: float | None = None,
    ) -> dict:
        """
        Train a new XGBoost model and upload to MinIO.
        Called by the Celery `retrain_predictor` task when ≥100 new samples.
        """
        if np is None:
            raise RuntimeError("numpy is required to train the XGBoost model")
        if joblib is None:
            raise RuntimeError("joblib is required to train and persist the XGBoost model")

        import xgboost as xgb
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        if len(set(y.tolist())) < 2:
            raise ValueError("Cannot train rejection predictor with only one outcome class")

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
        stratify = y if min(np.bincount(y.astype(int))) >= 2 else None
        X_train, X_valid, y_train, y_valid = train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
            stratify=stratify,
        )
        pipeline.fit(X_train, y_train)
        valid_prob = pipeline.predict_proba(X_valid)[:, 1]
        auc = float(roc_auc_score(y_valid, valid_prob)) if len(set(y_valid.tolist())) > 1 else 0.5

        baseline_auc = current_auc if current_auc is not None else self._auc
        if baseline_auc is not None and auc < (baseline_auc - settings.RETRAIN_MAX_AUC_DROP):
            log.warning(
                "Rejected candidate model because AUC regressed",
                candidate_auc=auc,
                baseline_auc=baseline_auc,
            )
            return {"promoted": False, "auc": auc, "baseline_auc": baseline_auc}

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
            self._auc = auc
            return {"promoted": True, "auc": auc, "version": version, "key": key}
        except Exception as exc:
            log.error("Failed to upload model to MinIO", error=str(exc))
            raise


# ── Singleton — loaded once per Celery worker startup ─────────────────────────
rejection_predictor = RejectionPredictor()
