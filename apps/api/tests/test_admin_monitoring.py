async def test_admin_and_monitoring(client):
    import json
    from uuid import uuid4

    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal
    from app.models import AuditLog
    from sqlalchemy import select

    health = await client.get('/health')
    assert health.status_code == 200
    assert health.json()['status'] == 'ok'

    login = await client.post('/api/v1/admin/login', json={'username': 'admin@wenshi.local', 'password': 'admin123456'})
    assert login.status_code == 200
    token = login.json()['access_token']

    code_response = await client.post('/api/v1/auth/code', json={'destination': 'feedback@example.com', 'channel': 'email', 'purpose': 'login'})
    user_login = await client.post('/api/v1/auth/login/code', json={'destination': 'feedback@example.com', 'channel': 'email', 'code': code_response.json()['mock_code']})
    user_token = user_login.json()['access_token']
    profiles = await client.get('/api/v1/profiles', headers={'Authorization': f'Bearer {user_token}'})
    self_profile = next(item for item in profiles.json() if item['relation'] == '本人')
    await client.patch(
        f"/api/v1/profiles/{self_profile['id']}",
        headers={'Authorization': f'Bearer {user_token}'},
        json={'name': '监控用户', 'gender': '女', 'birthday': '1993-08-16'},
    )
    await client.post(
        '/api/v1/profiles',
        headers={'Authorization': f'Bearer {user_token}'},
        json={'name': '家人档案', 'relation': '家人', 'gender': '男', 'birthday': '1989-02-12'},
    )
    feedback_response = await client.post(
        '/api/v1/feedback',
        headers={'Authorization': f'Bearer {user_token}'},
        json={
            'type': 'bug',
            'description': '反馈测试内容',
            'screenshot_urls': ['http://127.0.0.1:8000/uploads/feedback/test.jpg'],
            'app_version': '1.0.0',
            'platform': 'ios',
            'device_info': {'model': 'iPhone 15 Pro'},
        },
    )
    assert feedback_response.status_code == 201

    stats = await client.get('/api/v1/admin/stats', headers={'Authorization': f'Bearer {token}'})
    assert stats.status_code == 200
    assert 'users' in stats.json()
    assert stats.json()['feedback'] == 1

    feedback = await client.get('/api/v1/admin/feedback', headers={'Authorization': f'Bearer {token}'})
    assert feedback.status_code == 200
    assert feedback.json()['total'] == 1
    feedback_item = feedback.json()['items'][0]
    assert feedback_item['description'] == '反馈测试内容'
    assert feedback_item['user_contact'] == 'feedback@example.com'
    assert feedback_item['starred'] is False

    starred = await client.patch(
        f"/api/v1/admin/feedback/{feedback_item['id']}/star",
        headers={'Authorization': f'Bearer {token}'},
        json={'starred': True},
    )
    assert starred.status_code == 200
    assert starred.json()['starred'] is True

    status_response = await client.patch(
        f"/api/v1/admin/feedback/{feedback_item['id']}/status",
        headers={'Authorization': f'Bearer {token}'},
        json={'status': 'reviewing'},
    )
    assert status_response.status_code == 200
    assert status_response.json()['status'] == 'reviewing'

    async with AsyncSessionLocal() as session:
        admin_audit_logs = (
            await session.scalars(
                select(AuditLog)
                .where(AuditLog.action.in_(['admin.feedback.star', 'admin.feedback.status']))
                .order_by(AuditLog.created_at)
            )
        ).all()
    assert [item.action for item in admin_audit_logs] == ['admin.feedback.star', 'admin.feedback.status']
    assert admin_audit_logs[0].metadata_json == {'previous_starred': False, 'starred': True}
    assert admin_audit_logs[1].metadata_json == {'previous_status': 'open', 'status': 'reviewing'}

    filtered_feedback = await client.get(
        '/api/v1/admin/feedback?q=测试&feedback_type=bug&has_images=true&starred=true&feedback_status=reviewing',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert filtered_feedback.status_code == 200
    assert filtered_feedback.json()['total'] == 1

    analytics = await client.get('/api/v1/admin/analytics', headers={'Authorization': f'Bearer {token}'})
    assert analytics.status_code == 200
    analytics_json = analytics.json()
    assert len(analytics_json['daily']) == 14
    assert 'total_revenue_cents' in analytics_json['revenue']
    assert analytics_json['users']['real_users'] == 1
    assert analytics_json['users']['active_7d_users'] == 1
    assert analytics_json['users']['profile_completed_users'] == 1
    assert analytics_json['users']['profile_completion_rate'] == 100
    assert analytics_json['users']['average_profiles_per_user'] == 2
    assert {'label': 'email', 'count': 1} in analytics_json['users']['login_providers']
    assert {'label': '女', 'count': 1} in analytics_json['users']['gender_distribution']
    assert analytics_json['feedback']['total_feedback'] == 1
    assert analytics_json['feedback']['starred_feedback'] == 1
    assert analytics_json['feedback']['screenshot_feedback'] == 1
    assert {'label': 'bug', 'count': 1} in analytics_json['feedback']['type_distribution']
    assert {'label': 'ios', 'count': 1} in analytics_json['feedback']['platform_distribution']

    log_path = get_settings().log_path
    manual_request_id = f'manual-{uuid4()}'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as file:
        file.write('broken log line\n')
        file.write(json.dumps({'timestamp': '2026-05-05T00:00:00Z', 'level': 'error', 'event': 'manual.test', 'request_id': manual_request_id, 'status_code': 500, 'path': '/manual', 'duration_ms': 12.5}) + '\n')

    unauthenticated_logs = await client.get('/api/v1/admin/logs')
    assert unauthenticated_logs.status_code in {401, 403}

    logs_response = await client.get(f'/api/v1/admin/logs?level=error&q=manual&request_id={manual_request_id}&limit=10', headers={'Authorization': f'Bearer {token}'})
    assert logs_response.status_code == 200
    logs_json = logs_response.json()
    assert len(logs_json['items']) == 1
    assert logs_json['items'][0]['event'] == 'manual.test'
    assert logs_json['items'][0]['status_code'] == 500
    assert logs_json['items'][0]['path'] == '/manual'

    health_request_id = 'health-log-test'
    await client.get('/health', headers={'x-request-id': health_request_id})
    health_logs = await client.get(f'/api/v1/admin/logs?request_id={health_request_id}&limit=10', headers={'Authorization': f'Bearer {token}'})
    assert health_logs.status_code == 200
    assert any(item['event'] == 'http.request' and item['status_code'] == 200 for item in health_logs.json()['items'])

    me_request_id = 'me-user-log-test'
    await client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {user_token}', 'x-request-id': me_request_id})
    user_logs = await client.get(f'/api/v1/admin/logs?request_id={me_request_id}&limit=10', headers={'Authorization': f'Bearer {token}'})
    assert user_logs.status_code == 200
    assert any(item['raw'].get('user_id') for item in user_logs.json()['items'])

    metrics = await client.get('/metrics')
    assert metrics.status_code == 200
    assert 'wenshi_http_requests_total' in metrics.text
