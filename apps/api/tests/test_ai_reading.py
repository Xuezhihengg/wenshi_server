import json

from app.core.config import get_settings
from app.providers.llm import OpenAICompatibleLLMProvider
from app.services.records import build_ai_reading_messages

RECORD_PAYLOAD = {
    'id': 'front-record-1',
    'question': '事业能成吗',
    'createdAt': '2026-05-03T12:00:00+00:00',
    'hexagram': {
        'name': '屯',
        'changedName': '小过',
        'movingLineIndexes': [2],
        'lines': [
            {'index': index, 'sixKin': '父母', 'sixSpirit': '青龙', 'branch': '子', 'branchElement': '水', 'moving': index == 2, 'role': 'normal'}
            for index in range(6)
        ],
        'changedLines': [
            {'index': index, 'sixKin': '父母', 'sixSpirit': '青龙', 'branch': '子', 'branchElement': '水', 'moving': False, 'role': 'normal'}
            for index in range(6)
        ],
    },
    'lunarInfo': {
        'datetimeText': '丙午年 癸巳月 丁酉日',
        'dayStemBranch': '丁酉',
        'monthStemBranch': '癸巳',
        'yearStemBranch': '丙午',
        'timeStemBranch': '午',
        'voidBranches': ['辰', '巳'],
        'questionCategory': '事业',
    },
    'analysis': {
        'useGod': '官鬼',
        'useGodReason': '事业以官鬼为用神',
        'useGodLineIndexes': [2],
        'useGodHiddenLineIndexes': [],
        'strength': '用神得日生扶',
        'relation': '世应用神相生',
        'sanHe': '申子辰半合水局',
        'flyingHidden': '伏神不显',
        'progression': '动爻发动生用',
        'summary': '整体可成但需等待推动',
        'items': [{'title': '旺衰', 'value': '偏旺', 'detail': '日辰生扶'}],
        'spiritAnalyses': [
            {'title': '用神', 'sixKin': '官鬼', 'displayName': '官鬼子水', 'positionName': '三爻', 'lineIndex': 2, 'isHidden': False, 'verdict': '用神有根', 'strengthLabel': '偏旺', 'evidenceTags': ['日辰生扶'], 'reason': '事业看官鬼', 'detail': '官鬼得日扶'}
        ],
        'unionAnalysis': {
            'verdict': '半合待引',
            'summary': '水局有势但不全',
            'dominantElement': '水',
            'patterns': [
                {'kind': '半合', 'name': '申子辰水局', 'element': '水', 'status': '待引', 'verdict': '待引成势', 'impact': '有助用神', 'relationToUseGod': '生用神', 'participants': [], 'evidence': ['子水入局'], 'weakPoints': ['缺申辰']}
            ],
        },
    },
}


async def create_record(client, headers, question='事业能成吗'):
    response = await client.post('/api/v1/records', headers=headers, json={'question': question, 'payload': {**RECORD_PAYLOAD, 'question': question}})
    assert response.status_code == 201
    return response.json()


async def test_ai_reading_requires_auth(client):
    response = await client.post('/api/v1/records/00000000-0000-0000-0000-000000000000/ai-reading')
    assert response.status_code in {401, 403}


async def test_ai_reading_for_other_user_is_not_found(client, auth_headers):
    record = await create_record(client, auth_headers)
    other_code = await client.post('/api/v1/auth/code', json={'destination': '13900000000', 'channel': 'phone', 'purpose': 'login'})
    other_login = await client.post('/api/v1/auth/login/code', json={'destination': '13900000000', 'channel': 'phone', 'code': other_code.json()['mock_code']})
    other_headers = {'Authorization': f"Bearer {other_login.json()['access_token']}"}

    response = await client.post(f"/api/v1/records/{record['id']}/ai-reading", headers=other_headers)
    assert response.status_code == 404


async def test_ai_reading_generates_and_persists(monkeypatch, client, auth_headers):
    async def fake_create(self, messages, *, temperature=0.2, max_tokens=1200):
        user_payload = json.loads(messages[1]['content'])
        context = user_payload['context']
        assert context['analysis']['use_god'] == '官鬼'
        assert context['analysis']['spirit_analyses'][0]['title'] == '用神'
        assert context['analysis']['union_analysis']['patterns'][0]['name'] == '申子辰水局'
        return {
            'verdict': '此事可成但需待时',
            'expected_time_text': '近三日或子日见动静',
            'timeline': [
                {'type': 'cast', 'label': '起卦', 'time_text': context['time']['cast_at'], 'detail': '事业能成吗'},
                {'type': 'expected', 'label': '应期', 'time_text': '近三日或子日见动静', 'detail': '待水局引动'},
            ],
            'points': [
                {'claim': '用神有力', 'evidence': ['官鬼为用神', '日辰生扶'], 'explanation': '事业以官鬼为核心，用神得扶，事情有承接力。'},
            ],
            'status': 'ready',
        }

    monkeypatch.setenv('LLM_API_KEY', 'test-key')
    monkeypatch.setenv('LLM_PROVIDER', 'nvidia')
    get_settings.cache_clear()
    monkeypatch.setattr(OpenAICompatibleLLMProvider, 'create_json', fake_create)
    record = await create_record(client, auth_headers)

    response = await client.post(f"/api/v1/records/{record['id']}/ai-reading", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body['verdict'] == '此事可成但需待时'
    assert body['points'][0]['evidence'] == ['官鬼为用神', '日辰生扶']

    saved = await client.get(f"/api/v1/records/{record['id']}", headers=auth_headers)
    assert saved.status_code == 200
    assert saved.json()['ai_reading_status'] == 'ready'
    assert saved.json()['payload']['analysis']['aiReadingStructured']['expected_time_text'] == '近三日或子日见动静'


def test_prompt_contains_professional_context():
    class Note:
        fulfilled = True
        note = '三日后有回复'
        noted_at = None

    class Record:
        question = '事业能成吗'
        hexagram_name = '屯'
        changed_hexagram_name = '小过'
        cast_at = None
        payload = RECORD_PAYLOAD
        notes = [Note()]

    messages = build_ai_reading_messages(Record())
    user_payload = json.loads(messages[1]['content'])
    context = user_payload['context']
    assert context['analysis']['use_god'] == '官鬼'
    assert context['analysis']['spirit_analyses']
    assert context['analysis']['union_analysis']['patterns']
    assert context['verification_notes'][0]['note'] == '三日后有回复'
