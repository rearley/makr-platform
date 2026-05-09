import io
import boto3

_client = None
_bucket: str = ""


def init_storage(bucket: str, region: str, access_key: str, secret_key: str) -> None:
    global _client, _bucket
    _bucket = bucket
    _client = boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def _get_client():
    if _client is None:
        raise RuntimeError("Storage not initialised — call init_storage() in app.py before first use.")
    return _client


def upload_file(file_obj_or_path, key: str, content_type: str | None = None) -> None:
    """Upload a file-like object or local path to S3."""
    client = _get_client()
    extra = {"ContentType": content_type} if content_type else {}

    if isinstance(file_obj_or_path, (str, bytes)):
        client.upload_file(str(file_obj_or_path), _bucket, key, ExtraArgs=extra or None)
    else:
        client.upload_fileobj(file_obj_or_path, _bucket, key, ExtraArgs=extra or None)


def download_file(key: str) -> bytes:
    """Download a file from S3 and return its contents as bytes."""
    buf = io.BytesIO()
    _get_client().download_fileobj(_bucket, key, buf)
    return buf.getvalue()


def get_url(key: str, expires_in: int = 3600) -> str:
    """Return a presigned URL valid for `expires_in` seconds."""
    return _get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def delete_file(key: str) -> None:
    """Delete a file from S3."""
    _get_client().delete_object(Bucket=_bucket, Key=key)
