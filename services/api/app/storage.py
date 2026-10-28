"""
Storage abstraction supporting both local filesystem and S3/MinIO.
Allows running completely locally with zero external services/Docker.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class StorageClient:
    """Unified storage client for local filesystem and S3/MinIO."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.is_local = (
            self.settings.storage_backend == "local"
            or not self.settings.s3_endpoint_url
        )
        self.local_root = Path(self.settings.local_storage_dir)
        if self.is_local:
            self.local_root.mkdir(parents=True, exist_ok=True)

    def _get_s3_client(self) -> Any:
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key,
            aws_secret_access_key=self.settings.s3_secret_key,
            config=Config(signature_version="s3v4"),
        )

    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
        bucket: str | None = None,
    ) -> None:
        bucket = bucket or self.settings.s3_bucket
        if self.is_local:
            file_path = self.local_root / bucket / key
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(data)
            logger.info("stored_local_object", bucket=bucket, key=key, size=len(data))
        else:
            s3 = self._get_s3_client()
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata=metadata or {},
            )

    def get_object(self, key: str, bucket: str | None = None) -> bytes:
        bucket = bucket or self.settings.s3_bucket
        if self.is_local:
            file_path = self.local_root / bucket / key
            if not file_path.exists():
                raise FileNotFoundError(f"Object not found: {bucket}/{key}")
            return file_path.read_bytes()
        else:
            s3 = self._get_s3_client()
            resp = s3.get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()

    def delete_prefix(self, prefix: str, bucket: str | None = None) -> None:
        bucket = bucket or self.settings.s3_bucket
        if self.is_local:
            target_dir = self.local_root / bucket / prefix
            if target_dir.exists():
                import shutil
                if target_dir.is_dir():
                    shutil.rmtree(target_dir)
                else:
                    target_dir.unlink()
        else:
            s3 = self._get_s3_client()
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if keys:
                    s3.delete_objects(Bucket=bucket, Delete={"Objects": keys})

    def delete_object(self, key: str, bucket: str | None = None) -> None:
        bucket = bucket or self.settings.s3_bucket
        if self.is_local:
            file_path = self.local_root / bucket / key
            if file_path.exists():
                file_path.unlink()
        else:
            s3 = self._get_s3_client()
            s3.delete_object(Bucket=bucket, Key=key)


_storage_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client
