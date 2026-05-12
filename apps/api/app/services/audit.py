from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog

SENSITIVE_KEYS = {'destination', 'email', 'phone', 'mobile', 'reason', 'url'}


async def write_audit_log(db: AsyncSession, actor_user_id: str | None, action: str, target_type: str | None = None, target_id: str | None = None, metadata: dict | None = None) -> None:
    db.add(AuditLog(actor_user_id=actor_user_id, action=action, target_type=target_type, target_id=target_id, metadata_json=sanitize_audit_metadata(metadata)))


def sanitize_audit_metadata(metadata: dict | None) -> dict | None:
    if not metadata:
        return metadata
    return {key: _sanitize_value(key, value) for key, value in metadata.items()}


def _sanitize_value(key: str, value):
    if value is None:
        return None
    if isinstance(value, dict):
        return sanitize_audit_metadata(value)
    if isinstance(value, list):
        return [_sanitize_value(key, item) for item in value]
    if key in SENSITIVE_KEYS:
        return mask_sensitive(str(value))
    return value


def mask_sensitive(value: str) -> str:
    if '@' in value:
        name, domain = value.split('@', 1)
        if len(name) <= 2:
            masked_name = f'{name[:1]}***'
        else:
            masked_name = f'{name[:2]}***{name[-1:]}'
        return f'{masked_name}@{domain}'
    digits = ''.join(char for char in value if char.isdigit())
    if len(digits) >= 7:
        return f'{value[:3]}****{value[-4:]}'
    if len(value) > 12:
        return f'{value[:6]}***{value[-4:]}'
    return '***'
