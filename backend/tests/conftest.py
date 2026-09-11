import os
import sys
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

sys.path.append('/app/backend')


def _load_base_url() -> str:
    env_file = Path('/app/frontend/.env')
    frontend_env = dotenv_values(env_file) if env_file.exists() else {}
    base_url = (
        os.environ.get('EXPO_BACKEND_URL')
        or os.environ.get('EXPO_PUBLIC_BACKEND_URL')
        or frontend_env.get('EXPO_BACKEND_URL')
        or frontend_env.get('EXPO_PUBLIC_BACKEND_URL')
    )
    if not base_url:
        raise RuntimeError('Missing EXPO_BACKEND_URL/EXPO_PUBLIC_BACKEND_URL for API testing.')
    return str(base_url).rstrip('/')


@pytest.fixture(scope='session')
def base_url() -> str:
    return _load_base_url()


@pytest.fixture(scope='session')
def users():
    password = 'WarChess!2026'
    return {
        'king': {'email': 'king.warchess@example.com', 'name': 'Alden', 'password': password},
        'queen': {'email': 'queen.warchess@example.com', 'name': 'Mira', 'password': password},
        'rook': {'email': 'rook.warchess@example.com', 'name': 'Rowan', 'password': password},
        'bishop': {'email': 'bishop.warchess@example.com', 'name': 'Sage', 'password': password},
        'knight': {'email': 'knight.warchess@example.com', 'name': 'Kael', 'password': password},
        'pawn': {'email': 'pawn.warchess@example.com', 'name': 'Finn', 'password': password},
    }


@pytest.fixture(scope='session')
def api_client():
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    yield session
    session.close()


def login(api_client: requests.Session, base_url: str, user: dict) -> str:
    payload = {'email': user['email'], 'password': user['password']}
    response = api_client.post(f'{base_url}/api/auth/login', json=payload, timeout=20)
    if response.status_code == 401:
        reg = api_client.post(
            f'{base_url}/api/auth/register',
            json={**payload, 'name': user['name']},
            timeout=20,
        )
        if reg.status_code not in (200, 409):
            pytest.fail(f'Unable to register required account {user["email"]}: {reg.status_code} {reg.text}')
        response = api_client.post(f'{base_url}/api/auth/login', json=payload, timeout=20)
    assert response.status_code == 200, response.text
    return response.json()['token']


@pytest.fixture(scope='session')
def auth_tokens(api_client, base_url, users):
    return {role: login(api_client, base_url, data) for role, data in users.items()}


@pytest.fixture(scope='session')
def active_room_context(api_client, base_url, auth_tokens):
    """Create one real 6-player active room for integration checks and manual inspection."""
    king_headers = {'Authorization': f'Bearer {auth_tokens["king"]}'}
    created = api_client.post(
        f'{base_url}/api/rooms',
        headers=king_headers,
        json={'difficulty': 'easy'},
        timeout=20,
    )
    assert created.status_code == 200, created.text
    room = created.json()
    code = room['code']

    for role, token in auth_tokens.items():
        enter = api_client.post(
            f'{base_url}/api/rooms/{code}/enter',
            headers={'Authorization': f'Bearer {token}'},
            timeout=20,
        )
        assert enter.status_code == 200, enter.text

    for role, token in auth_tokens.items():
        role_pick = api_client.post(
            f'{base_url}/api/rooms/{code}/actions',
            headers={'Authorization': f'Bearer {token}'},
            json={'type': 'role', 'role': role},
            timeout=20,
        )
        assert role_pick.status_code == 200, role_pick.text

    for role, token in auth_tokens.items():
        ready = api_client.post(
            f'{base_url}/api/rooms/{code}/actions',
            headers={'Authorization': f'Bearer {token}'},
            json={'type': 'ready', 'ready': True},
            timeout=20,
        )
        assert ready.status_code == 200, ready.text

    # Wait briefly for active state transition to be reflected.
    for _ in range(20):
        state = api_client.get(
            f'{base_url}/api/rooms/{code}',
            headers=king_headers,
            timeout=20,
        )
        assert state.status_code == 200, state.text
        room = state.json()
        if room['status'] == 'active':
            break
        import time

        time.sleep(0.5)

    assert room['status'] == 'active', room
    Path('/app/test_reports/active_room_code.txt').write_text(code)
    return {'code': code, 'room': room}