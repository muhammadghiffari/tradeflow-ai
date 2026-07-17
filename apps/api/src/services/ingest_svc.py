"""
TradeFlow AI — Storage & Ingestion Service

PRD §1.6 — Handles file uploads, hashing, and storing to either Supabase or MinIO.
"""

import hashlib
import io
import mimetypes

import boto3
import structlog
from botocore.client import Config

from ..config import settings
from ..dependencies import get_supabase

log = structlog.get_logger()

class StorageService:
    def __init__(self):
        self.backend = settings.STORAGE_BACKEND
        self.bucket = settings.STORAGE_BUCKET_NAME
        self._bucket_initialized = False

        if self.backend == "minio":
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY.get_secret_value() if hasattr(settings.MINIO_SECRET_KEY, 'get_secret_value') else settings.MINIO_SECRET_KEY,
                config=Config(signature_version="s3v4", s3={'addressing_style': 'path'}),
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
                # MinIO buckets are private by default. Avoid overly restrictive IP-based
                # policies because the API container does not originate from localhost.
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
            
            # Skip bucket creation check because the bucket already exists
            # and the storage3 client may have buggy create_bucket payload formatting.

            await supabase.storage.from_(self.bucket).upload(
                object_path,
                file_bytes,
                {"content-type": content_type}
            )

            log.info("Uploaded to Supabase Storage", path=object_path)
            return object_path

        raise ValueError(f"Unknown storage backend: {self.backend}")

    async def download_document(self, object_path: str) -> bytes:
        """Download a document from the configured storage backend."""
        if self.backend == "minio":
            import asyncio

            def _download() -> bytes:
                response = self.s3_client.get_object(Bucket=self.bucket, Key=object_path)
                return response["Body"].read()

            return await asyncio.to_thread(_download)

        if self.backend == "supabase":
            supabase = get_supabase()
            data = await supabase.storage.from_(self.bucket).download(object_path)
            return bytes(data)

        raise ValueError(f"Unknown storage backend: {self.backend}")

    def compute_hash(self, file_bytes: bytes) -> str:
        """Compute SHA-256 hash of the file."""
        return hashlib.sha256(file_bytes).hexdigest()

    async def get_presigned_url(self, object_path: str, expires_in: int = 3600) -> str:
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
            res = await supabase.storage.from_(self.bucket).create_signed_url(object_path, expires_in)
            return res.get("signedURL", "")
        return ""

storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    global storage_service
    if storage_service is None:
        storage_service = StorageService()
    return storage_service
