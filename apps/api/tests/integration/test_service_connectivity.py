import boto3
import pytest
import redis as redis_py
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from src.config import settings
from src.main import app


@pytest.mark.integration
def test_redis_is_available():
    redis_client = redis_py.Redis.from_url(settings.REDIS_URL)
    assert redis_client.ping() is True


@pytest.mark.integration
def test_minio_bucket_and_object_lifecycle():
    minio_client = boto3.client(
        "s3",
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
    )

    bucket_name = settings.STORAGE_BUCKET_NAME

    # Verify bucket exists or create it if missing
    try:
        existing = [b["Name"] for b in minio_client.list_buckets().get("Buckets", [])]
    except ClientError as exc:
        pytest.skip(f"MinIO is unavailable: {exc}")

    if bucket_name not in existing:
        minio_client.create_bucket(Bucket=bucket_name)

    object_key = "integration/test.txt"
    body = b"integration test"

    minio_client.put_object(Bucket=bucket_name, Key=object_key, Body=body)
    response = minio_client.get_object(Bucket=bucket_name, Key=object_key)
    assert response["Body"].read() == body
    minio_client.delete_object(Bucket=bucket_name, Key=object_key)


@pytest.mark.integration
def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["environment"] == settings.ENVIRONMENT
