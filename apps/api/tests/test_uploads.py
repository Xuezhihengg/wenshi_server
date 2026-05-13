async def test_upload_avatar_returns_stable_url(client, auth_headers, tmp_path, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, 'upload_dir', str(tmp_path))
    monkeypatch.setattr(settings, 'public_base_url', 'http://test')

    response = await client.post(
        '/api/v1/uploads/avatar',
        headers={**auth_headers, 'host': '39.105.213.187'},
        files={'file': ('avatar.png', b'\x89PNG\r\n\x1a\navatar', 'image/png')},
    )

    assert response.status_code == 200
    url = response.json()['url']
    assert url.startswith('http://39.105.213.187/uploads/avatars/')
    path = tmp_path / url.removeprefix('http://39.105.213.187/uploads/')
    assert path.read_bytes() == b'\x89PNG\r\n\x1a\navatar'


async def test_upload_avatar_rejects_non_image(client, auth_headers):
    response = await client.post(
        '/api/v1/uploads/avatar',
        headers=auth_headers,
        files={'file': ('avatar.txt', b'not image', 'text/plain')},
    )

    assert response.status_code == 400
