import logging
import os
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

LOCAL_STORAGE_DIR = Path("./uploads")


class StorageService:
    """
    Unified storage service that uses AWS S3 when credentials/bucket are configured,
    or falls back to secure local file storage for local development and testing.
    """

    def __init__(self) -> None:
        self.bucket = settings.AWS_S3_BUCKET
        self.use_s3 = bool(
            settings.AWS_ACCESS_KEY_ID
            and settings.AWS_SECRET_ACCESS_KEY
            and settings.AWS_S3_BUCKET
        )
        if self.use_s3:
            self.s3_client = boto3.client(
                "s3",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
            )
            logger.info("StorageService: Initialized AWS S3 backend (bucket=%s)", self.bucket)
        else:
            self.s3_client = None
            LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            logger.info("StorageService: Initialized Local filesystem storage (dir=%s)", LOCAL_STORAGE_DIR)

    def upload_bytes(self, file_bytes: bytes, key: str, content_type: str) -> str:
        """Upload raw bytes to storage and return the storage key."""
        if self.use_s3 and self.s3_client:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
            )
            return key
        else:
            file_path = LOCAL_STORAGE_DIR / key
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(file_bytes)
            return key

    def download_bytes(self, key: str) -> bytes:
        """Download raw bytes from storage given a storage key."""
        if self.use_s3 and self.s3_client:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        else:
            file_path = LOCAL_STORAGE_DIR / key
            if not file_path.exists():
                raise FileNotFoundError(f"Storage key '{key}' not found in local storage.")
            return file_path.read_bytes()

    def generate_presigned_upload_url(
        self, key: str, content_type: str, expires_in: int = 3600
    ) -> dict:
        """Generate a pre-signed URL for direct browser-to-S3 upload."""
        if self.use_s3 and self.s3_client:
            try:
                url = self.s3_client.generate_presigned_url(
                    ClientMethod="put_object",
                    Params={
                        "Bucket": self.bucket,
                        "Key": key,
                        "ContentType": content_type,
                    },
                    ExpiresIn=expires_in,
                )
                return {
                    "upload_url": url,
                    "method": "PUT",
                    "key": key,
                    "headers": {"Content-Type": content_type},
                    "expires_in_seconds": expires_in,
                }
            except ClientError as e:
                logger.error("Failed to generate presigned upload URL: %s", e)
                raise
        else:
            # Local mock presigned response
            return {
                "upload_url": f"/v1/resumes/upload-direct?key={key}",
                "method": "POST",
                "key": key,
                "headers": {"Content-Type": content_type},
                "expires_in_seconds": expires_in,
            }

    def generate_presigned_download_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed URL for temporary file download."""
        if self.use_s3 and self.s3_client:
            return self.s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        return f"/v1/resumes/files/{key}"


storage_service = StorageService()
