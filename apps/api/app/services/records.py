import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models import FortuneRecord, Profile, User, VerificationNote
from app.providers.llm import get_llm_provider
from app.schemas.record import (
    AIReadingOut,
    RecordCreate,
    RecordUpdate,
    VerificationNoteIn,
    VerificationNoteUpdate,
)


def _hexagram_name(payload: dict, explicit: str | None) -> str | None:
    return explicit or payload.get('hexagram', {}).get('name')


def _changed_hexagram_name(payload: dict, explicit: str | None) -> str | None:
    return explicit or payload.get('hexagram', {}).get('changedName')


def _cast_at(payload: dict, explicit: datetime | None) -> datetime:
    if explicit:
        return explicit
    raw = payload.get('createdAt')
    if raw:
        try:
            return datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError:
            pass
    return datetime.now(UTC)


def _note_time(raw: str | None) -> datetime:
    if raw:
        try:
            return datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError:
            pass
    return datetime.now(UTC)


def _profile_payload(profile: Profile | None) -> dict | None:
    if not profile:
        return None
    return {
        'id': 'self' if profile.relation == '本人' else profile.id,
        'remoteId': profile.id,
        'name': profile.name,
        'relation': profile.relation,
        'gender': profile.gender,
        'birthday': profile.birthday,
        'avatarUri': profile.avatar_url,
    }


async def _sync_payload_profile(db: AsyncSession, record: FortuneRecord) -> None:
    profile = await db.get(Profile, record.profile_id) if record.profile_id else None
    profile_payload = _profile_payload(profile)
    if profile_payload is None:
        return
    record.payload = {**record.payload, 'profile': profile_payload}


def _valid_uuid(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None


def _compact_line(line: dict[str, Any]) -> dict[str, Any]:
    return {
        'index': line.get('index'),
        'six_kin': line.get('sixKin'),
        'six_spirit': line.get('sixSpirit'),
        'branch': line.get('branch') or line.get('stemBranch'),
        'element': line.get('branchElement'),
        'moving': line.get('moving'),
        'role': line.get('role'),
        'special_status': line.get('specialStatus'),
        'hidden_spirit': line.get('hiddenSpirit'),
    }


def _compact_spirit_analysis(item: dict[str, Any]) -> dict[str, Any]:
    return {
        'title': item.get('title'),
        'six_kin': item.get('sixKin'),
        'display_name': item.get('displayName'),
        'position_name': item.get('positionName'),
        'line_index': item.get('lineIndex'),
        'is_hidden': item.get('isHidden'),
        'verdict': item.get('verdict'),
        'strength_label': item.get('strengthLabel'),
        'evidence_tags': item.get('evidenceTags') or [],
        'reason': item.get('reason'),
        'detail': item.get('detail'),
    }


def _compact_union_pattern(item: dict[str, Any]) -> dict[str, Any]:
    return {
        'kind': item.get('kind'),
        'name': item.get('name'),
        'element': item.get('element'),
        'status': item.get('status'),
        'verdict': item.get('verdict'),
        'impact': item.get('impact'),
        'relation_to_use_god': item.get('relationToUseGod'),
        'participants': item.get('participants') or [],
        'evidence': item.get('evidence') or [],
        'weak_points': item.get('weakPoints') or [],
    }


def _ai_prompt_context(record: FortuneRecord) -> dict[str, Any]:
    payload = record.payload or {}
    analysis = payload.get('analysis') or {}
    hexagram = payload.get('hexagram') or {}
    lunar_info = payload.get('lunarInfo') or {}
    union_analysis = analysis.get('unionAnalysis') or {}
    return {
        'question': record.question,
        'hexagram': {
            'name': hexagram.get('name') or record.hexagram_name,
            'changed_name': hexagram.get('changedName') or record.changed_hexagram_name,
            'moving_line_indexes': hexagram.get('movingLineIndexes') or [],
            'lines': [_compact_line(line) for line in hexagram.get('lines') or []],
            'changed_lines': [_compact_line(line) for line in hexagram.get('changedLines') or []],
        },
        'time': {
            'cast_at': record.cast_at.isoformat() if record.cast_at else None,
            'lunar_text': lunar_info.get('datetimeText'),
            'year': lunar_info.get('yearStemBranch'),
            'month': lunar_info.get('monthStemBranch'),
            'day': lunar_info.get('dayStemBranch'),
            'hour': lunar_info.get('timeStemBranch'),
            'void_branches': lunar_info.get('voidBranches') or [],
            'question_category': lunar_info.get('questionCategory') or analysis.get('questionCategory'),
        },
        'analysis': {
            'use_god': analysis.get('useGod'),
            'use_god_reason': analysis.get('useGodReason'),
            'use_god_line_indexes': analysis.get('useGodLineIndexes') or [],
            'use_god_hidden_line_indexes': analysis.get('useGodHiddenLineIndexes') or [],
            'strength': analysis.get('strength'),
            'relation': analysis.get('relation'),
            'san_he': analysis.get('sanHe'),
            'flying_hidden': analysis.get('flyingHidden'),
            'progression': analysis.get('progression'),
            'summary': analysis.get('summary'),
            'items': analysis.get('items') or [],
            'spirit_analyses': [_compact_spirit_analysis(item) for item in analysis.get('spiritAnalyses') or []],
            'union_analysis': {
                'verdict': union_analysis.get('verdict'),
                'summary': union_analysis.get('summary'),
                'dominant_element': union_analysis.get('dominantElement'),
                'patterns': [_compact_union_pattern(item) for item in union_analysis.get('patterns') or []],
            },
        },
        'verification_notes': [
            {
                'fulfilled': note.fulfilled,
                'note': note.note,
                'noted_at': note.noted_at.isoformat() if note.noted_at else None,
            }
            for note in record.notes
        ],
    }


def build_ai_reading_messages(record: FortuneRecord, lang: str = 'zh') -> list[dict[str, str]]:
    context = _ai_prompt_context(record)
    if lang == 'en':
        system_prompt = (
            'You are a meticulous Liu Yao (Six-Line) divination analyst. Reason ONLY from the structured hexagram data the user provides; '
            'never invent lines, branches, six relatives, six spirits, union patterns, or notes that are not present. '
            'Output a single JSON object in ENGLISH. No Markdown. Conclusions should be assertive yet restrained; '
            'when evidence is insufficient, output exactly "Inconclusive". Each point must cite concrete hexagram evidence '
            '(e.g. Focus Spirit, World/Response, moving lines, month/day, void, month break, hidden movement, four spirits, '
            'union patterns, notes). Do not produce mystical filler.'
        )
        user_prompt = {
            'task': 'Generate analysis page content for the Wenshi divination app, in English',
            'output_schema': {
                'verdict': 'One assertive sentence as the main conclusion, max 24 words',
                'expected_time_text': 'Predicted timing text in English; if undeterminable, output "Inconclusive"',
                'timeline': [
                    {
                        'type': 'cast|expected|note',
                        'label': 'Cast|Timing|Note',
                        'time_text': 'Time or time description',
                        'detail': 'Optional short note',
                    }
                ],
                'points': [
                    {
                        'claim': 'A concrete claim, max 16 words',
                        'evidence': ['Up to two concrete evidence items from the hexagram'],
                        'explanation': 'Explanation grounded in evidence, max 50 words',
                    }
                ],
                'status': 'ready',
            },
            'constraints': [
                'At most 4 points',
                'Each evidence list has at most 2 items',
                'Timeline must include the Cast node',
                'If notes exist, timeline must include a Note node',
                'Do not encourage superstitious decisions; do not give definitive medical, legal, or financial advice',
                'All output strings (verdict, labels, claims, evidence, explanations, expected_time_text) MUST be in English',
                'Chinese hexagram terms (e.g. 用神, 世应, 日辰) should be rendered as English equivalents (Focus, World/Response, Day Branch)',
            ],
            'context': context,
        }
    else:
        system_prompt = (
            '你是一名严谨的六爻分析师。只基于用户提供的卦象结构化信息判断，禁止编造不存在的爻、地支、六亲、六神、合局或批注。'
            '输出必须是中文 JSON object，不要 Markdown。结论要断言式但克制；证据不足时直接写"不足以断"。'
            '每个论断必须引用具体卦象证据，例如用神、世应、动爻、月日、旬空、月破暗动、四神、合局、批注。'
            '不要输出长篇玄学套话。'
        )
        user_prompt = {
            'task': '生成问事 App 解析页内容',
            'output_schema': {
                'verdict': '一句断言式主结论，最多 32 个汉字',
                'expected_time_text': '应期预测文本；不能判断则写"不足以断"',
                'timeline': [
                    {
                        'type': 'cast|expected|note',
                        'label': '起卦|应期|批注',
                        'time_text': '时间或时间描述',
                        'detail': '可选的短说明',
                    }
                ],
                'points': [
                    {
                        'claim': '一个具体论断，最多 24 个汉字',
                        'evidence': ['最多两条来自卦象的具体证据'],
                        'explanation': '结合证据解释，最多 70 个汉字',
                    }
                ],
                'status': 'ready',
            },
            'constraints': [
                'points 最多 4 条',
                'evidence 每条最多 2 项',
                '必须包含起卦时间线节点',
                '若有批注，timeline 必须包含批注节点',
                '不要建议用户迷信决策，不要给医疗、法律、金融确定性建议',
            ],
            'context': context,
        }
    return [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': json.dumps(user_prompt, ensure_ascii=False, separators=(',', ':'))},
    ]


def _coerce_ai_reading(raw: dict[str, Any], record: FortuneRecord, lang: str = 'zh') -> AIReadingOut:
    now = datetime.now(UTC)
    is_en = lang == 'en'
    cast_label = 'Cast' if is_en else '起卦'
    expected_label = 'Timing' if is_en else '应期'
    inconclusive = 'Inconclusive' if is_en else '不足以断'
    timeline = raw.get('timeline') if isinstance(raw.get('timeline'), list) else []
    if not timeline:
        timeline = [
            {
                'type': 'cast',
                'label': cast_label,
                'time_text': record.cast_at.isoformat() if record.cast_at else now.isoformat(),
                'detail': record.question,
            }
        ]
    if raw.get('expected_time_text') and not any(item.get('type') == 'expected' for item in timeline if isinstance(item, dict)):
        timeline.append({'type': 'expected', 'label': expected_label, 'time_text': str(raw.get('expected_time_text')), 'detail': None})
    points = raw.get('points') if isinstance(raw.get('points'), list) else []
    payload = {
        'verdict': str(raw.get('verdict') or inconclusive),
        'expected_time_text': str(raw.get('expected_time_text')) if raw.get('expected_time_text') else None,
        'timeline': timeline[:8],
        'points': points[:4],
        'status': 'ready',
        'generated_at': now,
        'model': get_settings().llm_model,
        'lang': lang,
    }
    return AIReadingOut.model_validate(payload)


async def _replace_notes_from_payload(db: AsyncSession, record: FortuneRecord, payload: dict) -> None:
    notes = payload.get('verificationNotes')
    if notes is None:
        return
    await db.execute(delete(VerificationNote).where(VerificationNote.record_id == record.id))
    for note in notes:
        db.add(
            VerificationNote(
                record_id=record.id,
                fulfilled=bool(note.get('fulfilled', True)),
                note=note.get('note') or '',
                noted_at=_note_time(note.get('createdAt')),
            )
        )


async def upsert_record(db: AsyncSession, user: User, payload: RecordCreate) -> FortuneRecord:
    record_id = _valid_uuid(payload.id)
    record = await db.scalar(select(FortuneRecord).options(selectinload(FortuneRecord.notes)).where(FortuneRecord.id == record_id)) if record_id else None
    data = payload.payload
    if record:
        if record.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Record not found')
        record.profile_id = payload.profile_id
        record.question = payload.question
        record.hexagram_name = _hexagram_name(data, payload.hexagram_name)
        record.changed_hexagram_name = _changed_hexagram_name(data, payload.changed_hexagram_name)
        record.favorite = payload.favorite
        record.cast_at = _cast_at(data, payload.cast_at)
        record.payload = data
    else:
        record = FortuneRecord(
            id=record_id,
            user_id=user.id,
            profile_id=payload.profile_id,
            question=payload.question,
            hexagram_name=_hexagram_name(data, payload.hexagram_name),
            changed_hexagram_name=_changed_hexagram_name(data, payload.changed_hexagram_name),
            favorite=payload.favorite,
            cast_at=_cast_at(data, payload.cast_at),
            payload=data,
        )
        db.add(record)
        await db.flush()
    await _replace_notes_from_payload(db, record, data)
    await _sync_payload_profile(db, record)
    await db.commit()
    return await get_record(db, user, record.id)


async def get_record(db: AsyncSession, user: User, record_id: str) -> FortuneRecord:
    record = await db.scalar(select(FortuneRecord).options(selectinload(FortuneRecord.notes)).where(FortuneRecord.id == record_id, FortuneRecord.user_id == user.id))
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Record not found')
    return record


async def update_record(db: AsyncSession, user: User, record_id: str, payload: RecordUpdate) -> FortuneRecord:
    record = await get_record(db, user, record_id)
    data = payload.model_dump(exclude_unset=True)
    if 'payload' in data and data['payload'] is not None:
        record.payload = data['payload']
        record.hexagram_name = _hexagram_name(data['payload'], data.get('hexagram_name'))
        record.changed_hexagram_name = _changed_hexagram_name(data['payload'], data.get('changed_hexagram_name'))
        await _replace_notes_from_payload(db, record, data['payload'])
    for key in ['profile_id', 'question', 'hexagram_name', 'changed_hexagram_name', 'favorite', 'cast_at']:
        if key in data and data[key] is not None:
            setattr(record, key, data[key])
    await _sync_payload_profile(db, record)
    await db.commit()
    return await get_record(db, user, record_id)


async def generate_ai_reading(db: AsyncSession, user: User, record_id: str, lang: str = 'zh') -> AIReadingOut:
    record = await get_record(db, user, record_id)
    record.ai_reading_status = 'generating'
    await db.commit()
    provider = get_llm_provider()
    try:
        raw_reading = await provider.create_json(build_ai_reading_messages(record, lang=lang))
        reading = _coerce_ai_reading(raw_reading, record, lang=lang)
        payload = dict(record.payload or {})
        analysis = dict(payload.get('analysis') or {})
        analysis['aiReadingStructured'] = reading.model_dump(mode='json')
        payload['analysis'] = analysis
        record.payload = payload
        record.ai_reading_status = 'ready'
        await db.commit()
        return reading
    except HTTPException:
        record.ai_reading_status = 'failed'
        await db.commit()
        raise
    except Exception as exc:
        record.ai_reading_status = 'failed'
        await db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='AI reading generation failed') from exc


async def list_records(db: AsyncSession, user: User, limit: int, offset: int, favorite: bool | None = None, query: str | None = None) -> tuple[list[FortuneRecord], int]:
    stmt: Select = select(FortuneRecord).options(selectinload(FortuneRecord.notes)).where(FortuneRecord.user_id == user.id)
    count_stmt = select(func.count()).select_from(FortuneRecord).where(FortuneRecord.user_id == user.id)
    if favorite is not None:
        stmt = stmt.where(FortuneRecord.favorite == favorite)
        count_stmt = count_stmt.where(FortuneRecord.favorite == favorite)
    if query:
        pattern = f'%{query}%'
        stmt = stmt.where(FortuneRecord.question.ilike(pattern))
        count_stmt = count_stmt.where(FortuneRecord.question.ilike(pattern))
    total = await db.scalar(count_stmt) or 0
    items = list((await db.scalars(stmt.order_by(desc(FortuneRecord.cast_at)).limit(limit).offset(offset))).all())
    return items, total


async def toggle_favorite(db: AsyncSession, user: User, record_id: str) -> FortuneRecord:
    record = await get_record(db, user, record_id)
    record.favorite = not record.favorite
    await db.commit()
    return await get_record(db, user, record_id)


async def create_note(db: AsyncSession, user: User, record_id: str, payload: VerificationNoteIn) -> VerificationNote:
    record = await get_record(db, user, record_id)
    note = VerificationNote(record_id=record.id, fulfilled=payload.fulfilled, note=payload.note, noted_at=payload.noted_at or datetime.now(UTC))
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def update_note(db: AsyncSession, user: User, record_id: str, note_id: str, payload: VerificationNoteUpdate) -> VerificationNote:
    await get_record(db, user, record_id)
    note = await db.get(VerificationNote, note_id)
    if not note or note.record_id != record_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Note not found')
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(note, key, value)
    await db.commit()
    await db.refresh(note)
    return note


async def delete_note(db: AsyncSession, user: User, record_id: str, note_id: str) -> None:
    await get_record(db, user, record_id)
    note = await db.get(VerificationNote, note_id)
    if not note or note.record_id != record_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Note not found')
    await db.delete(note)
    await db.commit()
