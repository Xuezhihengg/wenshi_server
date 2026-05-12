async def test_profile_crud_record_notes_and_favorite(client, auth_headers):
    profiles = await client.get('/api/v1/profiles', headers=auth_headers)
    assert profiles.status_code == 200
    assert profiles.json()[0]['relation'] == '本人'

    created_profile = await client.post('/api/v1/profiles', headers=auth_headers, json={'name': '朋友', 'relation': '朋友', 'gender': '未填写', 'birthday': '未填写', 'is_selected': True})
    assert created_profile.status_code == 201
    profile_id = created_profile.json()['id']

    record_payload = {
        'profile_id': profile_id,
        'question': '事业能成吗',
        'favorite': False,
        'payload': {
            'id': 'front-record-1',
            'question': '事业能成吗',
            'createdAt': '2026-05-03T12:00:00+00:00',
            'hexagram': {'name': '屯', 'changedName': '小过'},
        },
    }
    record_response = await client.post('/api/v1/records', headers=auth_headers, json=record_payload)
    assert record_response.status_code == 201
    record = record_response.json()
    assert record['hexagram_name'] == '屯'

    favorite_response = await client.post(f"/api/v1/records/{record['id']}/favorite", headers=auth_headers)
    assert favorite_response.status_code == 200
    assert favorite_response.json()['favorite'] is True

    note_response = await client.post(f"/api/v1/records/{record['id']}/notes", headers=auth_headers, json={'fulfilled': True, 'note': '已应验'})
    assert note_response.status_code == 201
    assert note_response.json()['note'] == '已应验'

    list_response = await client.get('/api/v1/records?favorite=true', headers=auth_headers)
    assert list_response.status_code == 200
    assert list_response.json()['total'] == 1


async def test_membership_order_mock_callback(client, auth_headers):
    plans = await client.get('/api/v1/memberships/plans')
    assert plans.status_code == 200
    assert len(plans.json()) == 3

    order_response = await client.post('/api/v1/memberships/orders', headers=auth_headers, json={'plan': 'monthly', 'channel': 'mock'})
    assert order_response.status_code == 200
    order = order_response.json()
    assert order['status'] == 'pending'

    callback = await client.post('/api/v1/memberships/mock-callback', json={'provider_order_id': order['provider_order_id'], 'success': True})
    assert callback.status_code == 200
    assert callback.json()['status'] == 'paid'

    current = await client.get('/api/v1/memberships/current', headers=auth_headers)
    assert current.status_code == 200
    assert current.json()['status'] == 'active'
