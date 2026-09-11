import time
import uuid

import pytest


# Core API smoke + multiplayer integration coverage for WAR CHESS.


def _auth(token: str):
    return {'Authorization': f'Bearer {token}'}


def _post(api_client, base_url, token, path, payload):
    return api_client.post(
        f'{base_url}/api{path}',
        headers=_auth(token),
        json=payload,
        timeout=25,
    )


def _get(api_client, base_url, token, path):
    return api_client.get(f'{base_url}/api{path}', headers=_auth(token), timeout=25)


def test_health_stockfish_and_modes(api_client, base_url):
    response = api_client.get(f'{base_url}/api/health', timeout=20)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['status'] == 'ok'
    assert data['engine_available'] is True
    assert set(data['difficulties'].keys()) == {'easy', 'hard', 'extreme', 'regret'}
    assert data['difficulties']['easy']['depth'] < data['difficulties']['hard']['depth'] < data['difficulties']['extreme']['depth'] < data['difficulties']['regret']['depth']


def test_invalid_login_rejected(api_client, base_url):
    response = api_client.post(
        f'{base_url}/api/auth/login',
        json={'email': 'king.warchess@example.com', 'password': 'WrongPassword!2026'},
        timeout=20,
    )
    assert response.status_code == 401
    assert 'incorrect' in response.text.lower()


def test_session_me_logout_revocation(api_client, base_url, users):
    creds = users['king']
    login = api_client.post(
        f'{base_url}/api/auth/login',
        json={'email': creds['email'], 'password': creds['password']},
        timeout=20,
    )
    assert login.status_code == 200, login.text
    token = login.json()['token']

    me = api_client.get(
        f'{base_url}/api/auth/me', headers={'Authorization': f'Bearer {token}'}, timeout=20
    )
    assert me.status_code == 200, me.text
    assert me.json()['email'] == creds['email']

    logout = api_client.post(
        f'{base_url}/api/auth/logout',
        headers={'Authorization': f'Bearer {token}'},
        timeout=20,
    )
    assert logout.status_code == 200, logout.text

    revoked = api_client.get(
        f'{base_url}/api/auth/me', headers={'Authorization': f'Bearer {token}'}, timeout=20
    )
    assert revoked.status_code == 401


def test_voice_endpoint_returns_503_without_keys(api_client, base_url, active_room_context, auth_tokens):
    code = active_room_context['code']
    response = _post(api_client, base_url, auth_tokens['king'], f'/rooms/{code}/voice', {})
    assert response.status_code == 503
    assert 'livekit' in response.text.lower() or 'voice' in response.text.lower()


def test_role_lock_conflicts_and_autostart_constraints(api_client, base_url, auth_tokens, active_room_context):
    code = active_room_context['code']

    # One player cannot select a second role once assigned.
    second_role = _post(
        api_client,
        base_url,
        auth_tokens['king'],
        f'/rooms/{code}/actions',
        {'type': 'role', 'role': 'queen'},
    )
    assert second_role.status_code == 409

    # Occupied role cannot be taken by another player.
    occupied = _post(
        api_client,
        base_url,
        auth_tokens['queen'],
        f'/rooms/{code}/actions',
        {'type': 'role', 'role': 'king'},
    )
    assert occupied.status_code == 409

    # Match already active -> not in lobby anymore.
    state = _get(api_client, base_url, auth_tokens['king'], f'/rooms/{code}')
    assert state.status_code == 200
    room = state.json()
    assert room['status'] == 'active'
    assert len(room['players']) == 6


def test_seventh_membership_forbidden(api_client, base_url, active_room_context):
    code = active_room_context['code']
    email = f'test_extra_{uuid.uuid4().hex[:10]}@example.com'
    register = api_client.post(
        f'{base_url}/api/auth/register',
        json={'email': email, 'password': 'WarChess!2026', 'name': 'Extra'},
        timeout=25,
    )
    assert register.status_code == 200, register.text
    token = register.json()['token']

    enter = api_client.post(
        f'{base_url}/api/rooms/{code}/enter',
        headers={'Authorization': f'Bearer {token}'},
        timeout=20,
    )
    assert enter.status_code == 409


def test_ownership_stale_version_and_ai_turn_block(api_client, base_url, auth_tokens, active_room_context):
    code = active_room_context['code']

    state = _get(api_client, base_url, auth_tokens['king'], f'/rooms/{code}')
    assert state.status_code == 200, state.text
    room = state.json()
    start_version = room['position_version']

    # Anti-cheat ownership: Queen tries to move pawn piece.
    wrong_owner = _post(
        api_client,
        base_url,
        auth_tokens['queen'],
        f'/rooms/{code}/actions',
        {'type': 'move', 'uci': 'e2e4', 'position_version': start_version},
    )
    assert wrong_owner.status_code == 403

    # Pawn legal move.
    legal = _post(
        api_client,
        base_url,
        auth_tokens['pawn'],
        f'/rooms/{code}/actions',
        {'type': 'move', 'uci': 'e2e4', 'position_version': start_version},
    )
    assert legal.status_code == 200, legal.text
    room_after_human = legal.json()
    assert room_after_human['moves'][-1] == 'e2e4'

    # During AI turn, human moves should be blocked.
    blocked_during_ai = _post(
        api_client,
        base_url,
        auth_tokens['king'],
        f'/rooms/{code}/actions',
        {'type': 'move', 'uci': 'g1f3', 'position_version': room_after_human['position_version']},
    )
    assert blocked_during_ai.status_code == 409

    # Wait for AI move and strategy phase to resume.
    latest = room_after_human
    for _ in range(40):
        probe = _get(api_client, base_url, auth_tokens['king'], f'/rooms/{code}')
        assert probe.status_code == 200, probe.text
        latest = probe.json()
        if latest['phase'] == 'strategy' and latest['position_version'] > room_after_human['position_version']:
            break
        time.sleep(0.5)

    assert latest['phase'] == 'strategy'
    assert latest['position_version'] > room_after_human['position_version']
    assert len(latest['moves']) >= 2  # includes Stockfish response

    stale = _post(
        api_client,
        base_url,
        auth_tokens['pawn'],
        f'/rooms/{code}/actions',
        {'type': 'move', 'uci': 'd2d4', 'position_version': start_version},
    )
    assert stale.status_code == 409


def test_non_king_cannot_approve(api_client, base_url, auth_tokens, active_room_context):
    code = active_room_context['code']
    response = _post(
        api_client,
        base_url,
        auth_tokens['queen'],
        f'/rooms/{code}/actions',
        {'type': 'approval', 'request_id': 'non-existent', 'approve': True},
    )
    assert response.status_code == 403
