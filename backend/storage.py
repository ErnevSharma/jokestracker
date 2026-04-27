from uuid import uuid4

import boto3

from backend.config import R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME


def _get_client():
    """Get configured S3 client for R2."""
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    )


def upload(data: bytes, content_type: str, prefix: str = "audio") -> str:
    """Upload bytes to R2 and return the object key."""
    key = f"{prefix}/{uuid4()}"
    _get_client().put_object(
        Bucket=R2_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def download(key: str) -> tuple[bytes, str]:
    """Download file from R2. Returns (data, content_type)."""
    response = _get_client().get_object(Bucket=R2_BUCKET_NAME, Key=key)
    data = response["Body"].read()
    content_type = response.get("ContentType", "audio/webm")
    return data, content_type


def presigned_url(key: str, expires: int = 3600) -> str:
    """Generate presigned URL for R2 object."""
    return _get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": key},
        ExpiresIn=expires,
    )
