import asyncio
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import pytest
import websockets
from dotenv import dotenv_values
from pymongo import MongoClient


# Security + voice relay contract coverage for Jan 2026 release scope.


def _auth(token: str):
    return {'Authorization': f'Bearer {token}'}


def _ws_base(base_url: str) -> str:
    parsed = urlparse(base_url)
    scheme = 'wss' if parsed.scheme == 'https' else 'ws'
    return f'{scheme}://{parsed.netloc}'


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _login(api_client, base_url, user):
    response = api_client.post(
        f'{base_url}/api/auth/login',
        json={'email': user['email'], 'password': user['password']},
        timeout=20,
    )
    assert response.status_code == 200, response.text
    return response.json()['token']


def _provision_temp_user(api_client, base_url, name_prefix='QA'):
    email = f'test_iso_{uuid.uuid4().hex[:10]}@example.com'
    password = 'WarChess!2026'
    register = api_client.post(
        f'{base_url}/api/auth/register',
        json={'email': email, 'password': password, 'name': f'{name_prefix}-{uuid.uuid4().hex[:4]}'},
        timeout=20,
    )
    if register.status_code == 200:
        token = register.json()['token']
    else:
        assert register.status_code == 409, register.text
        token = _login(api_client, base_url, {'email': email, 'password': password})
    return {'email': email, 'password': password, 'token': token}


def _db_handles():
    backend_env = dotenv_values('/app/backend/.env')
    mongo_url = os.environ.get('MONGO_URL') or backend_env.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME') or backend_env.get('DB_NAME')
    if not mongo_url or not db_name:
        pytest.skip('MONGO_URL/DB_NAME unavailable for revocation/expiry simulation checks.')
    client = MongoClient(str(mongo_url).strip('"'))
    return client, client[str(db_name).strip('"')]


def _create_lobby_room(api_client, base_url, auth_tokens, roles=('king', 'queen')):
    created = api_client.post(
        f'{base_url}/api/rooms',
        headers=_auth(auth_tokens['king']),
        json={'difficulty': 'easy'},
        timeout=20,
    )
    assert created.status_code == 200, created.text
    code = created.json()['code']

    for role in roles:
        enter = api_client.post(
            f'{base_url}/api/rooms/{code}/enter',
            headers=_auth(auth_tokens[role]),
            timeout=20,
        )
        assert enter.status_code == 200, enter.text

    for role in roles:
        role_pick = api_client.post(
            f'{base_url}/api/rooms/{code}/actions',
            headers=_auth(auth_tokens[role]),
            json={'type': 'role', 'role': role},
            timeout=20,
        )
        assert role_pick.status_code == 200, role_pick.text

    return code


def _create_isolated_lobby_room(api_client, base_url, roles=('king', 'queen')):
    users = [
        _provision_temp_user(api_client, base_url, name_prefix=f'Host-{roles[0]}'),
        *[_provision_temp_user(api_client, base_url, name_prefix=f'Member-{role}') for role in roles[1:]],
    ]

    created = api_client.post(
        f'{base_url}/api/rooms',
        headers=_auth(users[0]['token']),
        json={'difficulty': 'easy'},
        timeout=20,
    )
    assert created.status_code == 200, created.text
    code = created.json()['code']

    tokens_by_role = {roles[0]: users[0]['token']}
    for idx, role in enumerate(roles[1:], start=1):
        join = api_client.post(
            f'{base_url}/api/rooms/{code}/enter',
            headers=_auth(users[idx]['token']),
            timeout=20,
        )
        assert join.status_code == 200, join.text
        tokens_by_role[role] = users[idx]['token']

    # Host enters explicitly to normalize contract across implementations.
    host_enter = api_client.post(
        f'{base_url}/api/rooms/{code}/enter',
        headers=_auth(users[0]['token']),
        timeout=20,
    )
    assert host_enter.status_code in (200, 409), host_enter.text

    for role in roles:
        role_pick = api_client.post(
            f'{base_url}/api/rooms/{code}/actions',
            headers=_auth(tokens_by_role[role]),
            json={'type': 'role', 'role': role},
            timeout=20,
        )
        assert role_pick.status_code == 200, role_pick.text

    return code, tokens_by_role


async def _open_state_ws(base_url: str, code: str, token: str, origin: str | None = None):
    ws = await websockets.connect(
        f'{_ws_base(base_url)}/api/ws/{code}',
        origin=origin,
        open_timeout=8,
        max_size=2_000_000,
    )
    await ws.send(json.dumps({'token': token}))
    return ws


async def _expect_state_ack(ws):
    """Require an authenticated state acknowledgement before progressing checks."""
    await ws.send(json.dumps({'type': 'ping'}))
    for _ in range(6):
        payload = await asyncio.wait_for(ws.recv(), timeout=5)
        if isinstance(payload, str):
            data = json.loads(payload)
            if data.get('type') == 'state':
                return data
    raise AssertionError('No state ack received for websocket authentication check.')


async def _drain_ws(ws, window_seconds=0.6):
    deadline = time.time() + window_seconds
    while time.time() < deadline:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.15)
        except asyncio.TimeoutError:
            continue
        except websockets.ConnectionClosed:
            break


async def _open_voice_ws(base_url: str, code: str, ticket: str):
    ws = await websockets.connect(
        f'{_ws_base(base_url)}/api/voice/ws/{code}',
        open_timeout=8,
        max_size=2_000_000,
    )
    await ws.send(json.dumps({'ticket': ticket}))
    return ws


def test_security_headers_and_public_health_contract(api_client, base_url):
    response = api_client.get(f'{base_url}/api/health', timeout=20)
    assert response.status_code == 200, response.text
    assert response.json() == {'status': 'ok'}
    assert response.headers.get('x-content-type-options') == 'nosniff'
    assert response.headers.get('x-frame-options') == 'DENY'
    assert 'content-security-policy' in response.headers


def test_health_details_requires_auth_and_voice_engine_flags(api_client, base_url, auth_tokens):
    denied = api_client.get(f'{base_url}/api/health/details', timeout=20)
    assert denied.status_code == 401

    ok = api_client.get(
        f'{base_url}/api/health/details',
        headers=_auth(auth_tokens['king']),
        timeout=20,
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()
    assert data['engine_available'] is True
    assert data['voice_configured'] is True


def test_public_leaderboards_hide_internal_identifiers(api_client, base_url):
    for role in ('king', 'queen', 'rook', 'bishop', 'knight', 'pawn'):
        response = api_client.get(f'{base_url}/api/leaderboards/{role}', timeout=20)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['role'] == role
        for player in body['players']:
            assert '_id' not in player
            assert 'user_id' not in player
            assert 'email' not in player


def test_voice_ticket_rejects_non_member_or_missing_role(api_client, base_url, auth_tokens, users):
    code, tokens = _create_isolated_lobby_room(api_client, base_url, roles=('king',))

    no_auth = api_client.post(f'{base_url}/api/rooms/{code}/voice', timeout=20)
    assert no_auth.status_code == 401

    outsider = _provision_temp_user(api_client, base_url, name_prefix='Outsider')
    outsider_ticket = api_client.post(
        f'{base_url}/api/rooms/{code}/voice',
        headers=_auth(outsider['token']),
        timeout=20,
    )
    assert outsider_ticket.status_code == 403

    queen = _provision_temp_user(api_client, base_url, name_prefix='NoRole')

    queen_enter = api_client.post(
        f'{base_url}/api/rooms/{code}/enter',
        headers=_auth(queen['token']),
        timeout=20,
    )
    assert queen_enter.status_code == 200, queen_enter.text

    no_role = api_client.post(
        f'{base_url}/api/rooms/{code}/voice',
        headers=_auth(queen['token']),
        timeout=20,
    )
    assert no_role.status_code == 403


def test_voice_ticket_wrong_room_reused_and_expired_denied(api_client, base_url, auth_tokens):
    code_a, tokens_a = _create_isolated_lobby_room(api_client, base_url, roles=('king', 'queen'))
    code_b, _ = _create_isolated_lobby_room(api_client, base_url, roles=('rook', 'bishop'))

    issued = api_client.post(
        f'{base_url}/api/rooms/{code_a}/voice',
        headers=_auth(tokens_a['king']),
        timeout=20,
    )
    assert issued.status_code == 200, issued.text
    ticket = issued.json()['ticket']

    async def scenario():
        wrong_room = await _open_voice_ws(base_url, code_b, ticket)
        denied_wrong = await asyncio.wait_for(wrong_room.recv(), timeout=5)
        await wrong_room.close()
        assert isinstance(denied_wrong, str) and 'error' in denied_wrong

        fresh = api_client.post(
            f'{base_url}/api/rooms/{code_a}/voice',
            headers=_auth(tokens_a['king']),
            timeout=20,
        )
        assert fresh.status_code == 200, fresh.text
        reusable = fresh.json()['ticket']

        first = await _open_voice_ws(base_url, code_a, reusable)
        ready = await asyncio.wait_for(first.recv(), timeout=5)
        assert isinstance(ready, str) and 'ready' in ready

        second = await _open_voice_ws(base_url, code_a, reusable)
        denied_reuse = await asyncio.wait_for(second.recv(), timeout=5)
        await second.close()
        assert isinstance(denied_reuse, str) and 'error' in denied_reuse
        await first.close()

    asyncio.run(scenario())

    exp = api_client.post(
        f'{base_url}/api/rooms/{code_a}/voice',
        headers=_auth(tokens_a['king']),
        timeout=20,
    )
    assert exp.status_code == 200, exp.text
    exp_ticket = exp.json()['ticket']

    client, db = _db_handles()
    try:
        db.voice_tickets.update_one(
            {'ticket_hash': _digest(exp_ticket)},
            {'$set': {'expires_at': datetime.now(timezone.utc) - timedelta(seconds=1)}},
        )
    finally:
        client.close()

    async def expired_case():
        sock = await _open_voice_ws(base_url, code_a, exp_ticket)
        denied = await asyncio.wait_for(sock.recv(), timeout=5)
        await sock.close()
        assert isinstance(denied, str) and 'error' in denied

    asyncio.run(expired_case())


def test_voice_pcm_frame_contract_and_no_same_sender_echo(api_client, base_url, auth_tokens):
    code, tokens = _create_isolated_lobby_room(api_client, base_url, roles=('king', 'queen'))
    first = api_client.post(f'{base_url}/api/rooms/{code}/voice', headers=_auth(tokens['king']), timeout=20)
    second = api_client.post(f'{base_url}/api/rooms/{code}/voice', headers=_auth(tokens['queen']), timeout=20)
    assert first.status_code == 200 and second.status_code == 200

    async def scenario():
        ws_king = await _open_voice_ws(base_url, code, first.json()['ticket'])
        ws_queen = await _open_voice_ws(base_url, code, second.json()['ticket'])
        try:
            await asyncio.wait_for(ws_king.recv(), timeout=5)  # ready
            await asyncio.wait_for(ws_queen.recv(), timeout=5)  # ready

            frame = b'\x00' * 2560
            await ws_king.send(frame)

            # Receiver gets exactly 2561 bytes (sender-slot prefix + pcm frame).
            incoming = None
            for _ in range(8):
                candidate = await asyncio.wait_for(ws_queen.recv(), timeout=5)
                if isinstance(candidate, (bytes, bytearray)):
                    incoming = candidate
                    break
            assert incoming is not None
            assert len(incoming) == 2561

            # Same-sender echo must not happen (text peer updates are allowed).
            saw_sender_binary = False
            deadline = time.time() + 1.5
            while time.time() < deadline:
                try:
                    candidate = await asyncio.wait_for(ws_king.recv(), timeout=0.3)
                    if isinstance(candidate, (bytes, bytearray)):
                        saw_sender_binary = True
                        break
                except asyncio.TimeoutError:
                    pass
            assert saw_sender_binary is False

            # Bad frame size should be dropped by closing sender socket.
            await ws_king.send(b'\x01' * 100)
            with pytest.raises((asyncio.TimeoutError, websockets.ConnectionClosed)):
                await asyncio.wait_for(ws_king.recv(), timeout=2)
        finally:
            await ws_queen.close()
            await ws_king.close()

    asyncio.run(scenario())


def test_voice_leave_updates_peer_roster(api_client, base_url, auth_tokens):
    code, tokens = _create_isolated_lobby_room(api_client, base_url, roles=('king', 'queen'))
    t1 = api_client.post(f'{base_url}/api/rooms/{code}/voice', headers=_auth(tokens['king']), timeout=20)
    t2 = api_client.post(f'{base_url}/api/rooms/{code}/voice', headers=_auth(tokens['queen']), timeout=20)
    assert t1.status_code == 200 and t2.status_code == 200

    async def scenario():
        king = await _open_voice_ws(base_url, code, t1.json()['ticket'])
        queen = await _open_voice_ws(base_url, code, t2.json()['ticket'])
        await asyncio.wait_for(king.recv(), timeout=5)
        await asyncio.wait_for(queen.recv(), timeout=5)

        # Consume roster updates until both peers are listed once.
        saw_pair = False
        for _ in range(8):
            payload = await asyncio.wait_for(king.recv(), timeout=5)
            if isinstance(payload, str):
                data = json.loads(payload)
                if data.get('type') == 'peers' and len(data.get('peers', [])) == 2:
                    saw_pair = True
                    break
        assert saw_pair

        await queen.send(json.dumps({'type': 'leave'}))
        await queen.close()

        saw_single = False
        for _ in range(8):
            payload = await asyncio.wait_for(king.recv(), timeout=5)
            if isinstance(payload, str):
                data = json.loads(payload)
                if data.get('type') == 'peers' and len(data.get('peers', [])) == 1:
                    saw_single = True
                    break
        assert saw_single
        await king.close()

    asyncio.run(scenario())


def test_sec001_logout_revokes_ws_without_client_ping(api_client, base_url, auth_tokens, users):
    code, tokens = _create_isolated_lobby_room(api_client, base_url, roles=('king', 'queen'))
    king_token = tokens['king']

    async def scenario():
        ws = await _open_state_ws(base_url, code, king_token)

        # Fresh session still works and handshake is fully authenticated.
        fresh = await _expect_state_ack(ws)
        assert fresh.get('realtime_version') == 2

        # Remove any buffered pre-logout replies to avoid false positives.
        await _drain_ws(ws)

        # Revoke by logout and do not send further pings from this socket.
        out = api_client.post(
            f'{base_url}/api/auth/logout',
            headers=_auth(king_token),
            timeout=20,
        )
        assert out.status_code == 200, out.text

        # Trigger unique post-logout event from another member.
        marker = f'SEC001_POST_LOGOUT_{uuid.uuid4().hex[:10]}'
        role_update = api_client.post(
            f'{base_url}/api/rooms/{code}/actions',
            headers=_auth(tokens['queen']),
            json={'type': 'chat', 'text': marker},
            timeout=20,
        )
        assert role_update.status_code == 200, role_update.text

        closed = False
        deadline = time.time() + 6
        while time.time() < deadline:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=1)
                if isinstance(message, str) and marker in message:
                    pytest.fail('Revoked websocket received post-logout protected chat marker.')
            except websockets.ConnectionClosed:
                closed = True
                break
            except asyncio.TimeoutError:
                continue
        assert closed, 'Revoked websocket did not close after logout + post-logout room event.'

    asyncio.run(scenario())


def test_sec001_session_expiry_sweep_closes_ws(api_client, base_url, users):
    # Create isolated account for expiry simulation to avoid impacting shared six-role accounts.
    email = f'test_sec001_{uuid.uuid4().hex[:8]}@example.com'
    register = api_client.post(
        f'{base_url}/api/auth/register',
        json={'email': email, 'password': users['king']['password'], 'name': 'Sec Sweep'},
        timeout=20,
    )
    if register.status_code not in (200, 409):
        pytest.skip(f'Unable to provision isolated sec account: {register.status_code}')

    login = api_client.post(
        f'{base_url}/api/auth/login',
        json={'email': email, 'password': users['king']['password']},
        timeout=20,
    )
    assert login.status_code == 200, login.text
    token = login.json()['token']

    created = api_client.post(
        f'{base_url}/api/rooms',
        headers=_auth(token),
        json={'difficulty': 'easy'},
        timeout=20,
    )
    assert created.status_code == 200, created.text
    code = created.json()['code']

    async def scenario():
        ws = await _open_state_ws(base_url, code, token)

        # Ensure socket is fully active before expiring the backing session.
        fresh = await _expect_state_ack(ws)
        assert fresh.get('type') == 'state'

        client, db = _db_handles()
        try:
            db.sessions.delete_one({'token_hash': _digest(token)})
        finally:
            client.close()

        # registry.sweep runs every 2s; socket should close without client heartbeat.
        closed = False
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                await asyncio.wait_for(ws.recv(), timeout=1)
            except websockets.ConnectionClosed:
                closed = True
                break
            except asyncio.TimeoutError:
                continue
        assert closed, 'Expired session websocket stayed open beyond sweep interval.'

    asyncio.run(scenario())


def test_sec001_bad_origin_denied_on_internal_ws(api_client, auth_tokens):
    internal_base = 'http://localhost:8001'
    code, tokens = _create_isolated_lobby_room(api_client, internal_base, roles=('king', 'queen'))

    async def scenario():
        # Direct backend (no proxy rewrite): malicious Origin must be rejected.
        denied = False
        try:
            bad = await _open_state_ws(internal_base, code, tokens['king'], origin='https://evil.example.com')
            try:
                await _expect_state_ack(bad)
            except (AssertionError, asyncio.TimeoutError, websockets.ConnectionClosed):
                denied = True
            await bad.close()
        except Exception:
            denied = True
        assert denied, 'Direct internal WS accepted malicious Origin unexpectedly.'

    asyncio.run(scenario())


def test_sec001_max_three_state_connections(api_client, base_url, auth_tokens):
    code, tokens = _create_isolated_lobby_room(api_client, base_url, roles=('king', 'queen'))

    async def scenario():
        sockets = []
        try:
            for _ in range(3):
                ws = await _open_state_ws(base_url, code, tokens['queen'])
                state = await _expect_state_ack(ws)
                assert state.get('realtime_version') == 2
                sockets.append(ws)

            fourth = await _open_state_ws(base_url, code, tokens['queen'])
            # Fourth must fail once handshake is attempted.
            fourth_closed = False
            try:
                await _expect_state_ack(fourth)
            except (AssertionError, asyncio.TimeoutError, websockets.ConnectionClosed):
                fourth_closed = True
            await fourth.close()
            assert fourth_closed, 'Fourth concurrent state websocket was not rejected.'
        finally:
            for ws in sockets:
                await ws.close()

    asyncio.run(scenario())


def test_account_deletion_contract_api(api_client, base_url):
    user = _provision_temp_user(api_client, base_url, name_prefix='DeleteFlow')
    token = user['token']

    me_before = api_client.get(f'{base_url}/api/auth/me', headers=_auth(token), timeout=20)
    assert me_before.status_code == 200, me_before.text

    wrong_confirmation = api_client.post(
        f'{base_url}/api/auth/delete-account',
        headers=_auth(token),
        json={'password': user['password'], 'confirmation': 'KEEP'},
        timeout=20,
    )
    assert wrong_confirmation.status_code == 400

    wrong_password = api_client.post(
        f'{base_url}/api/auth/delete-account',
        headers=_auth(token),
        json={'password': 'WrongPass!2026', 'confirmation': 'DELETE'},
        timeout=20,
    )
    assert wrong_password.status_code == 403

    removed = api_client.post(
        f'{base_url}/api/auth/delete-account',
        headers=_auth(token),
        json={'password': user['password'], 'confirmation': 'DELETE'},
        timeout=20,
    )
    assert removed.status_code == 200, removed.text
    data = removed.json()
    assert data.get('deleted') is True or data.get('deletion_requested') is True

    me_after = api_client.get(f'{base_url}/api/auth/me', headers=_auth(token), timeout=20)
    assert me_after.status_code == 401
