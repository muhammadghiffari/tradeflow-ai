"""
Tests for storage service security
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from src.services.ingest_svc import StorageService


def test_minio_bucket_created_private():
    """Test that MinIO bucket is created without adding a public bucket policy."""
    with patch("src.services.ingest_svc.boto3.client") as mock_s3:
        # Mock S3 client
        mock_client = MagicMock()
        mock_s3.return_value = mock_client
        
        # Mock head_bucket to raise (bucket doesn't exist)
        mock_client.head_bucket.side_effect = Exception("Not found")
        
        # Create storage service
        storage = StorageService()
        
        # Verify bucket creation was attempted
        mock_client.create_bucket.assert_called_once()
        
        # Verify no bucket policy was applied by default
        mock_client.put_bucket_policy.assert_not_called()


def test_minio_bucket_created_without_policy():
    """Test that MinIO bucket creation does not require an API-local policy."""
    with patch("src.services.ingest_svc.boto3.client") as mock_s3:
        mock_client = MagicMock()
        mock_s3.return_value = mock_client
        mock_client.head_bucket.side_effect = Exception("Not found")
        
        storage = StorageService()
        
        # Policy should not be created because MinIO is private by default.
        mock_client.put_bucket_policy.assert_not_called()


def test_minio_bucket_already_exists():
    """Test that storage service works with existing bucket."""
    with patch("src.services.ingest_svc.boto3.client") as mock_s3:
        mock_client = MagicMock()
        mock_s3.return_value = mock_client
        
        # Mock successful head_bucket (bucket exists)
        mock_client.head_bucket.return_value = True
        
        storage = StorageService()
        
        # Should not call create_bucket or put_bucket_policy
        mock_client.create_bucket.assert_not_called()
        mock_client.put_bucket_policy.assert_not_called()


def test_upload_document_streams_bytes_to_minio():
    """Test that upload_document writes bytes through the S3 client."""
    with patch("src.services.ingest_svc.boto3.client") as mock_s3:
        mock_client = MagicMock()
        mock_s3.return_value = mock_client
        mock_client.head_bucket.return_value = True

        storage = StorageService()

        with patch("src.services.ingest_svc.io.BytesIO") as mock_bytesio:
            mock_bytesio.return_value = MagicMock()
            with patch.object(storage, "compute_hash") as mock_hash:
                mock_hash.return_value = "abc123"
                import asyncio

                asyncio.run(storage.upload_document("batch", "doc", "file.txt", b"hello"))

                mock_client.upload_fileobj.assert_called_once()
                mock_bytesio.assert_called_once()
