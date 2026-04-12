import uuid
import boto3
from backend.config import R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME


def _client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    )


def upload(data: bytes, content_type: str, prefix: str = "audio") -> str:
    key = f"{prefix}/{uuid.uuid4()}"
    _client().put_object(
        Bucket=R2_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def download(key: str) -> tuple[bytes, str]:
    """Returns (data, content_type)."""
    response = _client().get_object(Bucket=R2_BUCKET_NAME, Key=key)
    data = response["Body"].read()
    content_type = response.get("ContentType", "audio/webm")
    return data, content_type


def presigned_url(key: str, expires: int = 3600) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": key},
        ExpiresIn=expires,
    )
