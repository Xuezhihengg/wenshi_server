import json
from collections.abc import Iterable
from datetime import date
from typing import Any

from app.core.config import get_settings
from app.schemas.admin import AdminLogItem, AdminLogPage


async def query_logs(
    log_date: str | None = None,
    level: str | None = None,
    query: str | None = None,
    request_id: str | None = None,
    limit: int = 200,
) -> AdminLogPage:
    selected_date = log_date or date.today().isoformat()
    normalized_level = level.lower() if level else None
    keyword = query.lower() if query else None
    items: list[AdminLogItem] = []
    for raw_line in _iter_log_lines(selected_date):
        if keyword and keyword not in raw_line.lower():
            continue
        parsed = _parse_log_line(raw_line)
        if parsed is None:
            continue
        if normalized_level and parsed.level.lower() != normalized_level:
            continue
        if request_id and parsed.request_id != request_id:
            continue
        items.append(parsed)
        if len(items) >= limit:
            break
    return AdminLogPage(date=selected_date, items=items)


def _iter_log_lines(log_date: str) -> Iterable[str]:
    settings = get_settings()
    path = settings.log_path_for_date(log_date)
    try:
        with path.open(encoding='utf-8') as file:
            lines = file.readlines()
    except FileNotFoundError:
        return
    for line in reversed(lines):
        line = line.strip()
        if line:
            yield line


def _parse_log_line(raw_line: str) -> AdminLogItem | None:
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    message = payload.get('message')
    event_data = _parse_message(message)
    merged = {**payload, **event_data}
    raw = _json_safe(merged)
    return AdminLogItem(
        timestamp=str(merged.get('timestamp') or merged.get('asctime') or ''),
        level=str(merged.get('level') or merged.get('levelname') or '').lower(),
        event=str(merged.get('event') or ''),
        logger=str(merged.get('logger') or merged.get('name') or ''),
        message=str(message or merged.get('event') or ''),
        request_id=_optional_str(merged.get('request_id')),
        status_code=_optional_int(merged.get('status_code')),
        path=_optional_str(merged.get('path')),
        duration_ms=_optional_float(merged.get('duration_ms')),
        raw=raw,
    )


def _parse_message(message: Any) -> dict[str, Any]:
    if not isinstance(message, str):
        return {}
    try:
        parsed = json.loads(message)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _json_safe(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, default=str))
