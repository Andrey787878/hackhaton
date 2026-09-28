"""Create private MinIO bucket before API startup."""
import time

from botocore.exceptions import BotoCoreError, ClientError

from app.storage import get_storage


def main():
    storage = get_storage()
    for attempt in range(30):
        try:
            try:
                storage.client.head_bucket(Bucket=storage.bucket)
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in {"404", "NoSuchBucket"}:
                    raise
                storage.client.create_bucket(Bucket=storage.bucket)
            try:
                storage.client.get_bucket_policy(Bucket=storage.bucket)
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in {"NoSuchBucketPolicy", "404"}:
                    raise
            else:
                storage.client.delete_bucket_policy(Bucket=storage.bucket)
            print("Private object bucket ready", flush=True)
            return
        except (BotoCoreError, ClientError, OSError):
            if attempt == 29:
                raise
            time.sleep(2)


if __name__ == "__main__":
    main()
