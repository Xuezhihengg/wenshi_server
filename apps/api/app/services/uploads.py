from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import User
from app.services.audit import write_audit_log

ALLOWED_IMAGE_TYPES = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
}


async def save_avatar_upload(db: AsyncSession, user: User, file: UploadFile, request: Request | None = None) -> str:
    return await save_image_upload(db, user, file, 'avatars', 'uploads.avatar', request)


async def save_feedback_image_upload(db: AsyncSession, user: User, file: UploadFile, request: Request | None = None) -> str:
    return await save_image_upload(db, user, file, 'feedback', 'uploads.feedback_image', request)


async def save_image_upload(db: AsyncSession, user: User, file: UploadFile, folder: str, audit_action: str, request: Request | None = None) -> str:
    settings = get_settings()
    extension = ALLOWED_IMAGE_TYPES.get(file.content_type or '')
    if not extension:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Only JPG, PNG, and WebP images are supported')

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Image file is empty')
    if len(content) > settings.max_avatar_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='Image file is too large')

    relative_dir = Path(folder) / str(user.id)
    upload_dir = Path(settings.upload_dir) / relative_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f'{uuid4().hex}{extension}'
    path = upload_dir / filename
    path.write_bytes(content)

    url_path = f'/uploads/{relative_dir.as_posix()}/{filename}'
    url = f'{_public_base_url(request, settings.public_base_url)}{url_path}'
    await write_audit_log(db, user.id, audit_action, 'user', user.id, {'folder': folder, 'filename': filename})
    await db.commit()
    return url


def _public_base_url(request: Request | None, fallback: str) -> str:
    if request is None:
        return fallback.rstrip('/')
    forwarded_proto = request.headers.get('x-forwarded-proto')
    forwarded_host = request.headers.get('x-forwarded-host')
    proto = forwarded_proto.split(',', 1)[0].strip() if forwarded_proto else request.url.scheme
    host = forwarded_host.split(',', 1)[0].strip() if forwarded_host else request.headers.get('host')
    if not host:
        return fallback.rstrip('/')
    return f'{proto}://{host}'.rstrip('/')
