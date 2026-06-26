from __future__ import annotations

import uuid

from app.config import settings


def _key(filename: str, prefix: str) -> str:
    return f"{prefix}/{uuid.uuid4()}/{filename}"


def presign_put(*, filename: str, content_type: str) -> dict:
    """Presigned PUT for a document upload. In mock mode (no S3 bucket) returns a fake URL so the
    flow is exercisable offline."""
    key = _key(filename, "uploads")
    if not settings.S3_BUCKET:
        return {"url": f"https://mock-s3.local/{key}", "s3_key": key, "fields": {}}

    import boto3

    client = boto3.client("s3", region_name=settings.AWS_REGION)
    url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=3600,
    )
    return {"url": url, "s3_key": key, "fields": {}}


def presign_get(*, s3_key: str) -> str:
    """Signed GET for downloading a stored object."""
    if not settings.S3_BUCKET:
        return f"https://mock-s3.local/{s3_key}"

    import boto3

    client = boto3.client("s3", region_name=settings.AWS_REGION)
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
        ExpiresIn=3600,
    )
