import uuid

import boto3
import pytest

from src.config import settings
from src.services.ingest_svc import StorageService


@pytest.mark.integration
@pytest.mark.asyncio
async def test_minio_storage_service_upload_and_presigned_url():
    storage = StorageService()
    batch_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    object_path = await storage.upload_document(batch_id, doc_id, "test.txt", b"integration storage test")

    assert object_path == f"documents/{batch_id}/{doc_id}/test.txt"

    presigned_url = storage.get_presigned_url(object_path, expires_in=60)
    assert isinstance(presigned_url, str)
    assert presigned_url.startswith("http")

    minio_client = boto3.client(
        "s3",
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
    )

    response = minio_client.get_object(Bucket=settings.STORAGE_BUCKET_NAME, Key=object_path)
    assert response["Body"].read() == b"integration storage test"
