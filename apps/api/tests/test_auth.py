async def test_login_refresh_and_me(client):
    code_response = await client.post('/api/v1/auth/code', json={'destination': 'test@example.com', 'channel': 'email', 'purpose': 'login'})
    assert code_response.status_code == 200
    mock_code = code_response.json()['mock_code']
    assert mock_code

    login_response = await client.post('/api/v1/auth/login/code', json={'destination': 'test@example.com', 'channel': 'email', 'code': mock_code})
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens['is_new_user'] is True

    me_response = await client.get('/api/v1/auth/me', headers={'Authorization': f"Bearer {tokens['access_token']}"})
    assert me_response.status_code == 200
    me = me_response.json()
    assert me['email'] == 'test@example.com'
    assert me['phone'] is None
    assert me['register_provider'] == 'email'
    assert me['created_at']
    assert me['last_login_at']

    refresh_response = await client.post('/api/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']})
    assert refresh_response.status_code == 200


async def test_protected_requires_token(client):
    response = await client.get('/api/v1/profiles')
    assert response.status_code == 401


async def test_email_code_generation_uses_email_provider(monkeypatch, client):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, 'phone_verification_provider', 'mock')
    monkeypatch.setattr(settings, 'email_verification_provider', 'aliyun_dm')

    async def fake_send_mail(self, email: str, code: str):  # noqa: ANN001
        assert email == 'random@example.com'
        assert code != '123456'
        assert len(code) == 6
        assert code.isdigit()

        class Body:
            request_id = 'dm-test-request'

        class Response:
            body = Body()

        return Response()

    monkeypatch.setattr('app.providers.verification.AliyunDmEmailVerificationProvider.__init__', lambda self: None)
    monkeypatch.setattr('app.providers.verification.AliyunDmEmailVerificationProvider._send_mail', fake_send_mail)

    code_response = await client.post('/api/v1/auth/code', json={'destination': 'random@example.com', 'channel': 'email', 'purpose': 'login'})
    assert code_response.status_code == 200
    assert code_response.json()['mock_code'] is None
    assert code_response.json()['message'] == 'Verification code sent'


async def test_dypns_phone_code_uses_provider_check(monkeypatch, client):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, 'phone_verification_provider', 'dypnsapi_sms')
    calls = {'sent': False, 'checked': False}

    async def fake_send_code(self, destination: str, channel: str, code: str):  # noqa: ANN001
        from app.providers.verification import VerificationDeliveryResult

        assert destination == '13911112222'
        assert channel == 'phone'
        calls['sent'] = True
        return VerificationDeliveryResult(destination=destination, channel=channel, provider='dypns_sms', request_id='dypns-send')

    async def fake_check_code(self, destination: str, channel: str, code: str):  # noqa: ANN001
        assert destination == '13911112222'
        assert channel == 'phone'
        assert code == '654321'
        calls['checked'] = True
        return True

    monkeypatch.setattr('app.providers.verification.AliyunDypnsSmsVerificationProvider.send_code', fake_send_code)
    monkeypatch.setattr('app.providers.verification.AliyunDypnsSmsVerificationProvider.check_code', fake_check_code)

    code_response = await client.post('/api/v1/auth/code', json={'destination': '13911112222', 'channel': 'phone', 'purpose': 'login'})
    assert code_response.status_code == 200
    assert code_response.json()['mock_code'] is None
    assert calls['sent'] is True

    login_response = await client.post('/api/v1/auth/login/code', json={'destination': '13911112222', 'channel': 'phone', 'code': '654321'})
    assert login_response.status_code == 200
    assert calls['checked'] is True


async def test_bind_phone_and_email_with_code(client, auth_headers):
    phone_code_response = await client.post('/api/v1/auth/bind/code', headers=auth_headers, json={'destination': '13900000000', 'channel': 'phone'})
    assert phone_code_response.status_code == 200
    phone_code = phone_code_response.json()['mock_code']

    phone_bind_response = await client.post('/api/v1/auth/bind', headers=auth_headers, json={'destination': '13900000000', 'channel': 'phone', 'code': phone_code})
    assert phone_bind_response.status_code == 200
    assert phone_bind_response.json()['phone'] == '13900000000'

    email_code_response = await client.post('/api/v1/auth/bind/code', headers=auth_headers, json={'destination': 'bind@example.com', 'channel': 'email'})
    assert email_code_response.status_code == 200
    email_code = email_code_response.json()['mock_code']

    email_bind_response = await client.post('/api/v1/auth/bind', headers=auth_headers, json={'destination': 'bind@example.com', 'channel': 'email', 'code': email_code})
    assert email_bind_response.status_code == 200
    assert email_bind_response.json()['email'] == 'bind@example.com'


async def test_audit_metadata_masks_sensitive_values(client, auth_headers):
    from app.db.session import AsyncSessionLocal
    from app.models import AuditLog
    from sqlalchemy import select

    email_code_response = await client.post('/api/v1/auth/bind/code', headers=auth_headers, json={'destination': 'secret-person@example.com', 'channel': 'email'})
    email_code = email_code_response.json()['mock_code']

    email_bind_response = await client.post('/api/v1/auth/bind', headers=auth_headers, json={'destination': 'secret-person@example.com', 'channel': 'email', 'code': email_code})
    assert email_bind_response.status_code == 200

    async with AsyncSessionLocal() as session:
        audit_log = await session.scalar(select(AuditLog).where(AuditLog.action == 'auth.bind_email'))
    assert audit_log is not None
    assert audit_log.metadata_json == {'destination': 'se***n@example.com'}


async def test_bind_rejects_destination_owned_by_another_user(client, auth_headers):
    code_response = await client.post('/api/v1/auth/code', json={'destination': 'taken@example.com', 'channel': 'email', 'purpose': 'login'})
    login_response = await client.post('/api/v1/auth/login/code', json={'destination': 'taken@example.com', 'channel': 'email', 'code': code_response.json()['mock_code']})
    assert login_response.status_code == 200

    bind_code_response = await client.post('/api/v1/auth/bind/code', headers=auth_headers, json={'destination': 'taken@example.com', 'channel': 'email'})
    assert bind_code_response.status_code == 409
    assert bind_code_response.json()['detail'] == '邮箱已经被注册过了'


async def test_verification_code_purpose_is_isolated(client, auth_headers):
    login_code_response = await client.post('/api/v1/auth/code', json={'destination': 'purpose@example.com', 'channel': 'email', 'purpose': 'login'})
    login_code = login_code_response.json()['mock_code']
    bind_response = await client.post('/api/v1/auth/bind', headers=auth_headers, json={'destination': 'purpose@example.com', 'channel': 'email', 'code': login_code})
    assert bind_response.status_code == 401

    bind_code_response = await client.post('/api/v1/auth/bind/code', headers=auth_headers, json={'destination': 'bind-purpose@example.com', 'channel': 'email'})
    bind_code = bind_code_response.json()['mock_code']
    login_response = await client.post('/api/v1/auth/login/code', json={'destination': 'bind-purpose@example.com', 'channel': 'email', 'code': bind_code})
    assert login_response.status_code == 401


async def test_verification_code_is_single_use(client):
    code_response = await client.post('/api/v1/auth/code', json={'destination': 'single-use@example.com', 'channel': 'email', 'purpose': 'login'})
    code = code_response.json()['mock_code']

    first_login = await client.post('/api/v1/auth/login/code', json={'destination': 'single-use@example.com', 'channel': 'email', 'code': code})
    assert first_login.status_code == 200

    second_login = await client.post('/api/v1/auth/login/code', json={'destination': 'single-use@example.com', 'channel': 'email', 'code': code})
    assert second_login.status_code == 401


async def test_verification_code_send_is_rate_limited(client):
    first_response = await client.post('/api/v1/auth/code', json={'destination': 'limited@example.com', 'channel': 'email', 'purpose': 'login'})
    assert first_response.status_code == 200

    second_response = await client.post('/api/v1/auth/code', json={'destination': 'limited@example.com', 'channel': 'email', 'purpose': 'login'})
    assert second_response.status_code == 429


async def test_verification_code_too_many_attempts_invalidates_code(monkeypatch, client):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, 'verification_code_max_attempts', 2)

    code_response = await client.post('/api/v1/auth/code', json={'destination': 'attempts@example.com', 'channel': 'email', 'purpose': 'login'})
    code = code_response.json()['mock_code']

    first_wrong = await client.post('/api/v1/auth/login/code', json={'destination': 'attempts@example.com', 'channel': 'email', 'code': '000000'})
    assert first_wrong.status_code == 401

    second_wrong = await client.post('/api/v1/auth/login/code', json={'destination': 'attempts@example.com', 'channel': 'email', 'code': '111111'})
    assert second_wrong.status_code == 401

    correct_after_lock = await client.post('/api/v1/auth/login/code', json={'destination': 'attempts@example.com', 'channel': 'email', 'code': code})
    assert correct_after_lock.status_code == 401


async def test_deactivate_account_marks_user_disabled(client):
    code_response = await client.post('/api/v1/auth/code', json={'destination': 'disabled@example.com', 'channel': 'email', 'purpose': 'login'})
    login_response = await client.post('/api/v1/auth/login/code', json={'destination': 'disabled@example.com', 'channel': 'email', 'code': code_response.json()['mock_code']})
    assert login_response.status_code == 200
    tokens = login_response.json()
    headers = {'Authorization': f"Bearer {tokens['access_token']}"}

    deactivate_response = await client.post('/api/v1/auth/deactivate', headers=headers, json={'reason': 'test cleanup'})
    assert deactivate_response.status_code == 200

    me_response = await client.get('/api/v1/auth/me', headers=headers)
    assert me_response.status_code == 401

    refresh_response = await client.post('/api/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']})
    assert refresh_response.status_code == 401

    next_code_response = await client.post('/api/v1/auth/code', json={'destination': 'disabled@example.com', 'channel': 'email', 'purpose': 'login'})
    assert next_code_response.status_code == 403


async def test_apple_login_verifies_identity_token(monkeypatch, client):
    def fake_verify(identity_token: str):
        assert identity_token == 'apple.identity.token.for.tests'
        return {'sub': 'apple-sub-1', 'email': 'apple@example.com'}

    monkeypatch.setattr('app.services.auth.verify_apple_identity_token', fake_verify)

    login_response = await client.post(
        '/api/v1/auth/login/apple',
        json={
            'apple_id': 'apple-sub-1',
            'identity_token': 'apple.identity.token.for.tests',
            'email': 'apple@example.com',
            'display_name': 'Apple 测试用户',
        },
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens['is_new_user'] is True
    assert tokens['profile_completed'] is False

    me_response = await client.get('/api/v1/auth/me', headers={'Authorization': f"Bearer {tokens['access_token']}"})
    assert me_response.status_code == 200
    me = me_response.json()
    assert me['apple_id'] == 'apple-sub-1'
    assert me['email'] == 'apple@example.com'
    assert me['register_provider'] == 'apple'

    second_response = await client.post('/api/v1/auth/login/apple', json={'identity_token': 'apple.identity.token.for.tests'})
    assert second_response.status_code == 200
    assert second_response.json()['is_new_user'] is False


async def test_apple_login_rejects_mismatched_user(monkeypatch, client):
    monkeypatch.setattr('app.services.auth.verify_apple_identity_token', lambda identity_token: {'sub': 'apple-sub-real'})

    response = await client.post(
        '/api/v1/auth/login/apple',
        json={'apple_id': 'apple-sub-client', 'identity_token': 'apple.identity.token.for.tests'},
    )
    assert response.status_code == 401


async def test_google_login_verifies_identity_token(monkeypatch, client):
    def fake_verify(identity_token: str):
        assert identity_token == 'google.identity.token.for.tests'
        return {
            'sub': 'google-sub-1',
            'email': 'google@example.com',
            'name': 'Google 测试用户',
            'picture': 'https://example.com/avatar.png',
        }

    monkeypatch.setattr('app.services.auth.verify_google_identity_token', fake_verify)

    login_response = await client.post(
        '/api/v1/auth/login/google',
        json={'identity_token': 'google.identity.token.for.tests'},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens['is_new_user'] is True
    assert tokens['profile_completed'] is False

    me_response = await client.get('/api/v1/auth/me', headers={'Authorization': f"Bearer {tokens['access_token']}"})
    assert me_response.status_code == 200
    me = me_response.json()
    assert me['google_id'] == 'google-sub-1'
    assert me['email'] == 'google@example.com'
    assert me['display_name'] == 'Google 测试用户'
    assert me['avatar_url'] == 'https://example.com/avatar.png'
    assert me['register_provider'] == 'google'

    second_response = await client.post('/api/v1/auth/login/google', json={'identity_token': 'google.identity.token.for.tests'})
    assert second_response.status_code == 200
    assert second_response.json()['is_new_user'] is False


async def test_google_login_binds_existing_email_user(monkeypatch, client):
    code_response = await client.post('/api/v1/auth/code', json={'destination': 'same-google@example.com', 'channel': 'email', 'purpose': 'login'})
    email_login = await client.post(
        '/api/v1/auth/login/code',
        json={'destination': 'same-google@example.com', 'channel': 'email', 'code': code_response.json()['mock_code']},
    )
    assert email_login.status_code == 200

    monkeypatch.setattr(
        'app.services.auth.verify_google_identity_token',
        lambda identity_token: {'sub': 'google-sub-same-email', 'email': 'same-google@example.com', 'name': 'Same Email'},
    )

    google_login = await client.post('/api/v1/auth/login/google', json={'identity_token': 'google.identity.token.for.tests'})
    assert google_login.status_code == 200
    assert google_login.json()['is_new_user'] is False

    me_response = await client.get('/api/v1/auth/me', headers={'Authorization': f"Bearer {google_login.json()['access_token']}"})
    assert me_response.status_code == 200
    me = me_response.json()
    assert me['email'] == 'same-google@example.com'
    assert me['google_id'] == 'google-sub-same-email'
    assert me['register_provider'] == 'email'


async def test_google_login_rejects_disabled_user(monkeypatch, client):
    monkeypatch.setattr(
        'app.services.auth.verify_google_identity_token',
        lambda identity_token: {'sub': 'google-sub-disabled', 'email': 'google-disabled@example.com'},
    )
    login_response = await client.post('/api/v1/auth/login/google', json={'identity_token': 'google.identity.token.for.tests'})
    assert login_response.status_code == 200
    tokens = login_response.json()
    deactivate_response = await client.post(
        '/api/v1/auth/deactivate',
        headers={'Authorization': f"Bearer {tokens['access_token']}"},
        json={'reason': 'test cleanup'},
    )
    assert deactivate_response.status_code == 200

    next_response = await client.post('/api/v1/auth/login/google', json={'identity_token': 'google.identity.token.for.tests'})
    assert next_response.status_code == 403
