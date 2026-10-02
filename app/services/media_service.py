import hashlib
import re
import shutil
import uuid
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_media_token
from app.models.media import MediaAsset
from app.schemas.content import MediaAssetOut

LOCAL = "local"
S3 = "s3"
_CHUNK_BYTES = 1024 * 1024
_SAFE_SUFFIX = re.compile(r"^\.[a-z0-9]{1,10}$")

_bucket_ready = False


def media_root() -> Path:
    return Path(settings.media_root).resolve()


def file_path(asset: MediaAsset) -> Path:
    return media_root() / asset.object_key


@lru_cache
def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        # Path-style addressing: MinIO-like servers have no per-bucket hostnames.
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            retries={"max_attempts": 2},
        ),
    )


def _ensure_bucket() -> None:
    global _bucket_ready
    if _bucket_ready:
        return
    client = _s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)
    _bucket_ready = True


def _s3_put(upload: UploadFile, object_key: str) -> None:
    _ensure_bucket()
    extra = {"ContentType": upload.content_type or "application/octet-stream"}
    if upload.filename:
        # Stored on the object so a presigned link opens it under its original name.
        extra["ContentDisposition"] = f"inline; filename*=UTF-8''{quote(upload.filename)}"
    _s3_client().upload_fileobj(upload.file, settings.s3_bucket, object_key, ExtraArgs=extra)


def _local_put(upload: UploadFile, object_key: str) -> None:
    destination = media_root() / object_key
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out:
        shutil.copyfileobj(upload.file, out, _CHUNK_BYTES)


def _remove(provider: str, bucket: str, object_key: str) -> None:
    if provider == S3:
        try:
            _s3_client().delete_object(Bucket=bucket, Key=object_key)
        except (BotoCoreError, ClientError):
            pass
    else:
        (media_root() / object_key).unlink(missing_ok=True)


def presigned_url(asset: MediaAsset) -> str:
    """A time-limited link straight to the object in the bucket."""
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": asset.bucket, "Key": asset.object_key},
        ExpiresIn=settings.media_url_expire_minutes * 60,
    )


def signed_url(asset_id: uuid.UUID) -> str:
    return f"/api/v1/media/{asset_id}/file?token={create_media_token(asset_id)}"


def to_out(asset: MediaAsset) -> MediaAssetOut:
    out = MediaAssetOut.model_validate(asset)
    out.url = signed_url(asset.id)
    return out


async def save_upload(
    db: AsyncSession, owner_user_id: uuid.UUID, course_id: uuid.UUID, upload: UploadFile
) -> MediaAsset:
    asset_id = uuid.uuid4()
    suffix = Path(upload.filename or "").suffix.lower()
    # The stored name is ours; only a harmless extension is kept from the client's filename.
    object_key = f"courses/{course_id}/{asset_id}{suffix if _SAFE_SUFFIX.match(suffix) else ''}"

    # The request body is already spooled to a temp file, so measure it before storing anything.
    max_bytes = settings.media_max_upload_mb * 1024 * 1024
    size = 0
    digest = hashlib.sha256()
    while chunk := await upload.read(_CHUNK_BYTES):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File is larger than {settings.media_max_upload_mb} MB",
            )
        digest.update(chunk)
    if size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")
    await upload.seek(0)

    provider = settings.storage_provider
    bucket = settings.s3_bucket if provider == S3 else LOCAL
    try:
        await run_in_threadpool(_s3_put if provider == S3 else _local_put, upload, object_key)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media storage is unavailable",
        ) from exc

    try:
        asset = MediaAsset(
            id=asset_id,
            owner_user_id=owner_user_id,
            course_id=course_id,
            storage_provider=provider,
            bucket=bucket,
            object_key=object_key,
            original_filename=(upload.filename or "")[:255] or None,
            mime_type=(upload.content_type or "")[:120] or None,
            size_bytes=size,
            checksum=digest.hexdigest(),
            status="READY",
        )
        db.add(asset)
        await db.commit()
    except BaseException:
        await run_in_threadpool(_remove, provider, bucket, object_key)
        raise

    await db.refresh(asset)
    return asset


async def get_course_asset(
    db: AsyncSession, course_id: uuid.UUID, asset_id: uuid.UUID
) -> MediaAsset:
    """A lesson may only point at a file uploaded to its own course."""
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Media asset not found in this course",
        )
    return asset
