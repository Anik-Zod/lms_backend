import hashlib
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_media_token
from app.models.media import MediaAsset
from app.schemas.content import MediaAssetOut

STORAGE_PROVIDER = "local"
BUCKET = "local"
_CHUNK_BYTES = 1024 * 1024
_SAFE_SUFFIX = re.compile(r"^\.[a-z0-9]{1,10}$")


def media_root() -> Path:
    return Path(settings.media_root).resolve()


def file_path(asset: MediaAsset) -> Path:
    return media_root() / asset.object_key


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
    object_key = f"{asset_id}{suffix if _SAFE_SUFFIX.match(suffix) else ''}"

    root = media_root()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / object_key

    max_bytes = settings.media_max_upload_mb * 1024 * 1024
    size = 0
    digest = hashlib.sha256()
    try:
        with destination.open("wb") as out:
            while chunk := await upload.read(_CHUNK_BYTES):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File is larger than {settings.media_max_upload_mb} MB",
                    )
                digest.update(chunk)
                await run_in_threadpool(out.write, chunk)
        if size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

        asset = MediaAsset(
            id=asset_id,
            owner_user_id=owner_user_id,
            course_id=course_id,
            storage_provider=STORAGE_PROVIDER,
            bucket=BUCKET,
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
        destination.unlink(missing_ok=True)
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
