"""Live foreground PCM voice over WSS. Audio is transient RAM only, never recorded."""
import asyncio
import json
import secrets
from contextlib import suppress
from datetime import timedelta
from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from pymongo.errors import DuplicateKeyError
from database import db
from auth import current_user, digest
from realtime import registry, rate_limit, now, WORKER_ID, member_allowed

router = APIRouter()
rooms = {}
MAX_FRAME = 2560  # 80ms PCM16 mono at 16kHz.
MAX_VOICE_ROOMS = 40


async def voice_access(code, user_id):
    room = await db.rooms.find_one({'code': code}, {'_id': 0, 'players': 1, 'members': 1})
    if not member_allowed(room, user_id):
        raise HTTPException(403, 'Join this alliance before using voice.')
    player = next((p for p in room['players'].values() if p['id'] == user_id), None)
    if not player:
        raise HTTPException(403, 'Choose a role before joining team voice.')
    return player


@router.post('/rooms/{code}/voice')
async def issue_ticket(code: str, authorization: str = Header(default=''), user=Depends(current_user)):
    code = code.upper()
    await rate_limit(f'voice-ticket:{user["id"]}', 20)
    await voice_access(code, user['id'])
    raw = secrets.token_urlsafe(40)
    await db.voice_tickets.insert_one({'ticket_hash': digest(raw), 'session_hash': digest(authorization.removeprefix('Bearer ')), 'user_id': user['id'], 'code': code, 'expires_at': now() + timedelta(seconds=60), 'used': False})
    return {'ticket': raw, 'code': code, 'transport': 'wss-pcm16', 'sample_rate': 16000, 'frame_ms': 80, 'expires_in': 60}


async def own_room(code):
    try:
        value = await db.voice_room_leases.find_one_and_update(
            {'_id': code, '$or': [{'expires_at': {'$lte': now()}}, {'worker': WORKER_ID}]},
            {'$set': {'worker': WORKER_ID, 'expires_at': now() + timedelta(seconds=15)}}, upsert=True, return_document=True)
        return value['worker'] == WORKER_ID
    except DuplicateKeyError:
        return False


async def roster(code):
    peers = rooms.get(code, {})
    packet = {'type': 'peers', 'peers': [{'id': p['slot'], 'name': p['name'], 'role': p['role'], 'muted': p['muted']} for p in peers.values() if p['connection'].active]}
    for peer in list(peers.values()):
        enqueue(peer, packet)


def enqueue(peer, payload):
    queue = peer['queue']
    if queue.full():
        with suppress(asyncio.QueueEmpty):
            queue.get_nowait()
    queue.put_nowait(payload)


async def send_audio(peer):
    connection = peer['connection']
    while connection.active:
        payload = await peer['queue'].get()
        if not connection.active:
            break
        async with connection.send_lock:
            if isinstance(payload, bytes):
                await asyncio.wait_for(connection.socket.send_bytes(payload), 0.8)
            else:
                await asyncio.wait_for(connection.socket.send_json(payload), 0.8)


async def renew_voice_room(code, connection):
    while connection.active:
        if not await own_room(code):
            await registry.close(connection, 1013)
            return
        await asyncio.sleep(5)


@router.websocket('/voice/ws/{code}')
async def voice_socket(socket: WebSocket, code: str):
    if not await registry.admit(socket):
        return
    pending = True
    connection = None
    sender = None
    renewer = None
    code = code.upper()
    try:
        raw = await asyncio.wait_for(socket.receive_text(), 8)
        if len(raw) > 1024:
            raise HTTPException(400, 'Invalid voice handshake.')
        hello = json.loads(raw)
        if not isinstance(hello, dict):
            raise HTTPException(400, 'Invalid voice handshake.')
        ticket = await db.voice_tickets.find_one_and_update(
            {'ticket_hash': digest(str(hello.get('ticket', ''))), 'code': code, 'used': False, 'expires_at': {'$gt': now()}},
            {'$set': {'used': True}}, return_document=True, projection={'_id': 0})
        if not ticket:
            raise HTTPException(401, 'Voice invitation expired. Tap Join voice again.')
        player = await voice_access(code, ticket['user_id'])
        if code not in rooms and len(rooms) >= MAX_VOICE_ROOMS:
            raise HTTPException(429, 'Voice is at capacity. Please try again shortly.')
        if not await own_room(code):
            raise HTTPException(503, 'Voice room is reconnecting. Please retry.')
        connection = await registry.register(socket, ticket['user_id'], ticket['session_hash'], code, 'voice')
        registry.pending -= 1
        pending = False
        peers = rooms.setdefault(code, {})
        occupied = {p['slot'] for p in peers.values()}
        free = next((slot for slot in range(6) if slot not in occupied), None)
        if free is None:
            raise HTTPException(429, 'The six-person voice room is full.')
        peer = {'connection': connection, 'slot': free, 'name': player['name'], 'role': player['role'], 'muted': False, 'queue': asyncio.Queue(maxsize=6)}
        peers[socket] = peer
        await socket.send_json({'type': 'ready', 'slot': free, 'sample_rate': 16000, 'frame_ms': 80})
        sender = asyncio.create_task(send_audio(peer))
        renewer = asyncio.create_task(renew_voice_room(code, connection))
        def stop_failed_task(task):
            if not task.cancelled() and task.exception() is not None:
                asyncio.create_task(registry.close(connection, 1011))
        sender.add_done_callback(stop_failed_task)
        renewer.add_done_callback(stop_failed_task)
        await roster(code)
        while connection.active:
            message = await socket.receive()
            if message['type'] == 'websocket.disconnect':
                break
            if not registry.allow_message(connection, 180):
                raise HTTPException(429, 'Audio frame rate exceeded.')
            frame = message.get('bytes')
            if frame is not None:
                if len(frame) != MAX_FRAME:
                    await registry.close(connection, 1009)
                    break
                if peer['muted']:
                    continue
                packet = bytes([free]) + frame
                for other in list(peers.values()):
                    if other is not peer and other['connection'].active:
                        enqueue(other, packet)
            else:
                text = message.get('text', '')
                if len(text) > 512:
                    raise HTTPException(400, 'Invalid voice message.')
                command = json.loads(text)
                if not isinstance(command, dict):
                    raise HTTPException(400, 'Invalid voice command.')
                if command.get('type') == 'mute':
                    peer['muted'] = command.get('muted') is True
                    await roster(code)
                elif command.get('type') == 'leave':
                    break
    except HTTPException as error:
        with suppress(Exception):
            await socket.send_json({'type': 'error', 'message': error.detail})
            await socket.close(code=4001 if error.status_code in (401, 403) else 1008)
    except (WebSocketDisconnect, asyncio.TimeoutError, ValueError, RuntimeError):
        with suppress(Exception):
            await socket.close(code=1008)
    finally:
        if pending:
            registry.pending = max(0, registry.pending - 1)
        for task in (sender, renewer):
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await task
        rooms.get(code, {}).pop(socket, None)
        await registry.remove(socket)
        if not rooms.get(code):
            rooms.pop(code, None)
            await db.voice_room_leases.delete_one({'_id': code, 'worker': WORKER_ID})
        else:
            await roster(code)