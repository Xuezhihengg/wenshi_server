from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import AuditLog, Feedback, PortalVisit, User
from sqlalchemy import select


async def test_public_feedback_enters_admin_panel_and_rate_limits(client):
    response = await client.post(
        '/api/v1/public/feedback',
        headers={'x-forwarded-for': '203.0.113.8', 'user-agent': 'Portal Test Browser'},
        json={
            'type': 'feature',
            'description': '希望官网可以展示更多问事功能介绍',
            'name': '官网访客',
            'email': 'visitor@example.com',
            'language': 'zh',
        },
    )
    assert response.status_code == 201
    assert response.json()['platform'] == 'web'
    assert response.json()['app_version'] == 'portal'
    assert response.json()['screenshot_urls'] == []

    settings = get_settings()
    login = await client.post(
        '/api/v1/admin/login',
        json={'username': settings.admin_username, 'password': settings.admin_password},
    )
    token = login.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    feedback = await client.get('/api/v1/admin/feedback?q=visitor@example.com&feedback_type=feature', headers=headers)
    assert feedback.status_code == 200
    assert feedback.json()['total'] == 1
    feedback_item = feedback.json()['items'][0]
    assert feedback_item['user_display_name'] == 'Portal Visitor'
    assert feedback_item['user_contact'] == 'visitor@example.com'
    assert feedback_item['platform'] == 'web'

    analytics = await client.get('/api/v1/admin/analytics', headers=headers)
    assert {'label': 'web', 'count': 1} in analytics.json()['feedback']['platform_distribution']

    async with AsyncSessionLocal() as session:
        portal_user = await session.scalar(select(User).where(User.email == 'portal@wenshi.local'))
        feedback_row = await session.scalar(select(Feedback).where(Feedback.id == response.json()['id']))
        audit_log = await session.scalar(select(AuditLog).where(AuditLog.action == 'feedback.public_create'))
    assert portal_user is not None
    assert feedback_row is not None
    assert feedback_row.device_info['source'] == 'portal'
    assert feedback_row.device_info['user_agent'] == 'Portal Test Browser'
    assert audit_log is not None

    for index in range(4):
        limited_response = await client.post(
            '/api/v1/public/feedback',
            headers={'x-forwarded-for': '203.0.113.8'},
            json={'type': 'other', 'description': f'继续提交门户反馈内容 {index}'},
        )
        assert limited_response.status_code == 201

    rejected = await client.post(
        '/api/v1/public/feedback',
        headers={'x-forwarded-for': '203.0.113.8'},
        json={'type': 'other', 'description': '第六次提交应该触发限速'},
    )
    assert rejected.status_code == 429


async def test_public_feedback_validation(client):
    response = await client.post(
        '/api/v1/public/feedback',
        json={'type': 'invalid', 'description': 'short'},
    )
    assert response.status_code == 422


async def test_public_portal_visit_enters_admin_traffic(client):
    unauthenticated = await client.get('/api/v1/admin/portal-traffic')
    assert unauthenticated.status_code in {401, 403}

    response = await client.post(
        '/api/v1/public/portal-visit',
        headers={'x-forwarded-for': '198.51.100.10', 'user-agent': 'Portal Browser'},
        json={
            'path': '/?lang=en&utm_source=newsletter',
            'language': 'en',
            'referrer': 'https://example.com/article',
            'utm_source': 'newsletter',
            'utm_medium': 'email',
            'utm_campaign': 'launch',
            'session_id': 'session-public-test',
            'metadata': {'screen': '1440x900'},
        },
    )
    assert response.status_code == 201
    assert response.json()['language'] == 'en'
    assert response.json()['session_id'] == 'session-public-test'

    settings = get_settings()
    login = await client.post(
        '/api/v1/admin/login',
        json={'username': settings.admin_username, 'password': settings.admin_password},
    )
    headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
    traffic = await client.get('/api/v1/admin/portal-traffic?days=7', headers=headers)
    assert traffic.status_code == 200
    traffic_json = traffic.json()
    assert traffic_json['total_visits'] == 1
    assert traffic_json['unique_visitors'] == 1
    assert traffic_json['sessions'] == 1
    assert traffic_json['today_visits'] == 1
    assert {'label': 'en', 'count': 1} in traffic_json['language_distribution']
    assert {'label': 'newsletter', 'count': 1} in traffic_json['source_distribution']

    async with AsyncSessionLocal() as session:
        visit = await session.scalar(select(PortalVisit).where(PortalVisit.session_id == 'session-public-test'))
    assert visit is not None
    assert visit.ip_hash
    assert visit.user_agent == 'Portal Browser'
