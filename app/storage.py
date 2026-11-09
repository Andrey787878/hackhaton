from functools import lru_cache
import os

import boto3
from botocore.config import Config

from app.config import get_settings


class ObjectStorage:
    def __init__(self):
        settings = get_settings()
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=os.environ.get("S3_ENDPOINT_URL", "http://minio:9000"),
            aws_access_key_id=settings.minio_root_user,
            aws_secret_access_key=settings.minio_root_password,
            region_name="us-east-1",
            config=Config(signature_version="s3v4", retries={"max_attempts": 2},
                          connect_timeout=3, read_timeout=15, s3={"addressing_style": "path"}),
        )

    def put(self, key: str, body, size: int, content_type: str):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body,
                               ContentLength=size, ContentType=content_type)

    def delete(self, key: str):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def get(self, key: str):
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"]


@lru_cache(maxsize=1)
def get_storage() -> ObjectStorage:
    return ObjectStorage()
