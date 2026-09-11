import subprocess

import pytest
from dotenv import dotenv_values


# Deployment-readiness config checks for gitignore and protected env behavior.


def _check_ignore(path: str) -> str:
    result = subprocess.run(
        ['git', 'check-ignore', '--no-index', '-v', path],
        cwd='/app',
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def test_gitignore_allows_managed_env_files():
    assert _check_ignore('/app/backend/.env') == ''
    assert _check_ignore('/app/frontend/.env') == ''


def test_gitignore_still_blocks_private_local_env_overrides():
    backend_local = _check_ignore('/app/backend/.env.local')
    frontend_local = _check_ignore('/app/frontend/.env.local')
    assert '.env*.local' in backend_local
    assert '.env*.local' in frontend_local


# Backend and frontend protected env values remain intact; CORS setting explicitly present.


def test_backend_env_contains_explicit_cors_and_protected_keys():
    backend_env = dotenv_values('/app/backend/.env')
    assert backend_env.get('CORS_ORIGINS') == '*'
    assert backend_env.get('MONGO_URL') == 'mongodb://localhost:27017'
    assert backend_env.get('DB_NAME') == 'test_database'


def test_frontend_env_protected_urls_unchanged():
    frontend_env = dotenv_values('/app/frontend/.env')
    assert frontend_env.get('EXPO_PACKAGER_PROXY_URL') == 'https://six-role-battle.preview.emergentagent.com'
    assert frontend_env.get('EXPO_PACKAGER_HOSTNAME') == 'https://six-role-battle.preview.emergentagent.com'
    assert frontend_env.get('EXPO_PUBLIC_BACKEND_URL')


# CORS, health, and auth smoke through internal and external API routes.


def test_health_internal_and_external_show_ready(api_client, base_url):
    internal = api_client.get('http://localhost:8001/api/health', timeout=20)
    assert internal.status_code == 200, internal.text
    internal_data = internal.json()
    assert internal_data['status'] == 'ok'
    assert internal_data['engine'] == 'Stockfish'
    assert internal_data['engine_available'] is True
    assert internal_data['voice_configured'] is False

    external = api_client.get(f'{base_url}/api/health', timeout=20)
    assert external.status_code == 200, external.text
    external_data = external.json()
    assert external_data['status'] == 'ok'
    assert external_data['engine'] == 'Stockfish'
    assert external_data['engine_available'] is True
    assert external_data['voice_configured'] is False


@pytest.mark.parametrize('path', ['/api/auth/login', '/api/rooms'])
def test_options_preflight_returns_expected_cors_headers(api_client, base_url, path):
    headers = {
        'Origin': 'https://deploy-check.example.com',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'authorization,content-type',
    }
    response = api_client.options(f'{base_url}{path}', headers=headers, timeout=20)
    assert response.status_code == 200, response.text
    assert response.headers.get('access-control-allow-origin') == '*'
    allowed_headers = (response.headers.get('access-control-allow-headers') or '').lower()
    assert 'authorization' in allowed_headers
    assert 'content-type' in allowed_headers
    allowed_methods = (response.headers.get('access-control-allow-methods') or '').upper()
    assert 'POST' in allowed_methods
    assert 'GET' in allowed_methods
    assert response.headers.get('access-control-allow-credentials') in (None, 'false', 'False')


def test_get_health_with_origin_has_cors_and_no_cookie(api_client, base_url):
    origin = 'https://deploy-check.example.com'
    response = api_client.get(
        f'{base_url}/api/health',
        headers={'Origin': origin},
        timeout=20,
    )
    assert response.status_code == 200, response.text
    assert response.headers.get('access-control-allow-origin') in ('*', origin)
    assert response.headers.get('access-control-allow-credentials') in (None, 'false', 'False')
    assert 'set-cookie' not in {k.lower() for k in response.headers.keys()}


def test_auth_smoke_login_me_and_rooms(api_client, base_url):
    login = api_client.post(
        f'{base_url}/api/auth/login',
        json={'email': 'king.warchess@example.com', 'password': 'WarChess!2026'},
        timeout=20,
    )
    assert login.status_code == 200, login.text
    token = login.json()['token']

    me = api_client.get(
        f'{base_url}/api/auth/me',
        headers={'Authorization': f'Bearer {token}'},
        timeout=20,
    )
    assert me.status_code == 200, me.text
    me_data = me.json()
    assert me_data['email'] == 'king.warchess@example.com'

    rooms = api_client.get(
        f'{base_url}/api/rooms',
        headers={'Authorization': f'Bearer {token}'},
        timeout=20,
    )
    assert rooms.status_code == 200, rooms.text
    assert isinstance(rooms.json(), list)


def test_livekit_known_limitation_unchanged(api_client, base_url):
    health = api_client.get(f'{base_url}/api/health', timeout=20)
    assert health.status_code == 200, health.text
    assert health.json()['voice_configured'] is False
