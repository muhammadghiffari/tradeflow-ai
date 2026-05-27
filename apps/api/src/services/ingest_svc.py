"""
TradeFlow AI — Storage & Ingestion Service

PRD §1.6 — Handles file uploads, hashing, and storing to either Supabase or MinIO.
"""

import hashlib
import io
import mimetypes
import uuid
from typing import Literal

import boto3
from botocore.client import Config
import structlog

from ..config import settings
from ..dependencies import get_supabase

log = structlog.get_logger()

class StorageService:
    def __init__(self):
        self.backend = settings.STORAGE_BACKEND
        self.bucket = settings.STORAGE_BUCKET_NAME

        if self.backend == "minio":
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                config=Config(signature_version="s3v4"),
                region_name="us-east-1",
            )
            self._ensure_minio_bucket()
        else:
            # For supabase storage, we'll use the async supabase client provided by dependencies
            self.s3_client = None

    def _ensure_minio_bucket(self) -> None:
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket)
                # Make public for dev simplicity
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{self.bucket}/*"]
                        }
                    ]
                }
                import json
                self.s3_client.put_bucket_policy(Bucket=self.bucket, Policy=json.dumps(policy))
                log.info("Created MinIO bucket", bucket=self.bucket)
            except Exception as e:
                log.error("Failed to create bucket", error=str(e))

    async def upload_document(
        self, batch_id: str, doc_id: str, filename: str, file_bytes: bytes
    ) -> str:
        """Upload a document to the configured storage backend and return the path."""
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        object_path = f"documents/{batch_id}/{doc_id}/{filename}"

        if self.backend == "minio":
            self.s3_client.upload_fileobj(
                io.BytesIO(file_bytes),
                self.bucket,
                object_path,
                ExtraArgs={"ContentType": content_type}
            )
            log.info("Uploaded to MinIO", path=object_path)
            return object_path

        elif self.backend == "supabase":
            supabase = get_supabase()
            # Note: storage uploads are synchronous in python supabase client atm,
            # but we run it inside our async path. Ideally wrap in asyncio.to_thread
            import asyncio
            
            def _upload():
                # Ensure bucket exists
                buckets = supabase.storage.list_buckets()
                if not any(b.name == self.bucket for b in buckets):
                    supabase.storage.create_bucket(self.bucket, {"public": False})
                
                res = supabase.storage.from_(self.bucket).upload(
                    object_path,
                    file_bytes,
                    {"content-type": content_type}
                )
                return res

            await asyncio.to_thread(_upload)
            log.info("Uploaded to Supabase Storage", path=object_path)
            return object_path
        
        raise ValueError(f"Unknown storage backend: {self.backend}")

    def compute_hash(self, file_bytes: bytes) -> str:
        """Compute SHA-256 hash of the file."""
        return hashlib.sha256(file_bytes).hexdigest()

    def get_presigned_url(self, object_path: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for preview/download."""
        if self.backend == "minio":
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": object_path},
                ExpiresIn=expires_in,
            )
        elif self.backend == "supabase":
            # For Supabase, we can use create_signed_url
            supabase = get_supabase()
            res = supabase.storage.from_(self.bucket).create_signed_url(object_path, expires_in)
            return res.get("signedURL", "")
        return ""

storage_service = StorageService()
