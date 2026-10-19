"""Initialize the local S3-compatible object store used by Docker Compose.

This is intentionally a one-shot infrastructure command. It creates the private
media bucket if it does not exist and verifies that the server is reachable.
Browser CORS is configured on the MinIO server itself because current community
builds do not implement the S3 PutBucketCors API. It never creates sample objects.
"""
from __future__ import annotations

import os
import sys
import time

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, EndpointConnectionError


ENDPOINT = os.getenv("OBJECT_STORAGE_ENDPOINT", "http://minio:9000")
ACCESS_KEY = os.environ["OBJECT_STORAGE_ACCESS_KEY"]
SECRET_KEY = os.environ["OBJECT_STORAGE_SECRET_KEY"]
BUCKET = os.getenv("OBJECT_STORAGE_BUCKET", "lodge-crm-media")
REGION = os.getenv("OBJECT_STORAGE_REGION", "us-east-1")

s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION,
    config=BotoConfig(signature_version="s3v4", connect_timeout=3, read_timeout=5),
)


def wait_for_server(max_attempts: int = 60) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            # list_buckets validates both network reachability and credentials.
            s3.list_buckets()
            return
        except (EndpointConnectionError, ClientError) as exc:
            if attempt == max_attempts:
                raise RuntimeError(f"Object storage did not become ready: {exc}") from exc
            time.sleep(2)


def ensure_bucket() -> None:
    try:
        s3.head_bucket(Bucket=BUCKET)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"404", "NoSuchBucket", "NotFound"} or status == 404:
            # MinIO accepts the simple CreateBucket form for its default region.
            s3.create_bucket(Bucket=BUCKET)
        else:
            raise

    # Bucket existence is the only initialization required here.
    # CORS for direct browser/presigned requests is configured via
    # MINIO_API_CORS_ALLOW_ORIGIN on the MinIO service.



if __name__ == "__main__":
    try:
        wait_for_server()
        ensure_bucket()
        print(f"Object storage ready. Private bucket ensured: {BUCKET}")
    except Exception as exc:  # one-shot command must fail hard for Compose dependency gating
        print(f"Object storage initialization failed: {exc}", file=sys.stderr)
        raise
