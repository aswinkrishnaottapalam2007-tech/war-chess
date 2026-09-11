import asyncio
import logging
import os
import time
import json
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from fastapi import FastAPI, APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from database import db, client
from auth import router as auth_router, current_user, authenticate, digest
from game_service import create_room, enter_room, get_room, require_access, action, sockets, clock_loop, room_lock, save
from rules import ROLES, member, public_state
from engine import STRENGTH, ENGINE_PATH
from realtime import registry, rate_limit
from voice_relay import router as voice_router
from http_security import SecurityHeadersMiddleware
from account_cleanup import cleanup_loop

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app):
    await db.users.create_index('email', unique=True)
    await db.sessions.create_index('token_hash', unique=True)
    await db.sessions.create_index('expires_at', expireAfterSeconds=0)
    await db.rooms.create_index('code', unique=True)
    await db.results.create_index('round_id', unique=True)
    await db.presence.create_index([('code', 1), ('user_id', 1)], unique=True)
    await db.auth_limits.create_index('key', unique=True)
    await db.auth_limits.create_index('expires_at', expireAfterSeconds=0)
    await db.api_limits.create_index('key', unique=True)
    await db.api_limits.create_index('expires_at', expireAfterSeconds=0)
    await db.socket_leases.create_index('expires_at', expireAfterSeconds=0)
    await db.voice_tickets.create_index('ticket_hash', unique=True)
    await db.voice_tickets.create_index('expires_at', expireAfterSeconds=0)
    await db.voice_room_leases.create_index('expires_at', expireAfterSeconds=0)
    task = asyncio.create_task(clock_loop())
    sweep = asyncio.create_task(registry.sweep())
    deletions = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()
    sweep.cancel()
    deletions.cancel()
    with suppress(asyncio.CancelledError):
        await task
    with suppress(asyncio.CancelledError):
        await sweep
    with suppress(asyncio.CancelledError):
        await deletions
    for connection in list(registry.live.values()):
        await registry.close(connection, 1001)
    client.close()


app = FastAPI(title='WAR CHESS Authoritative API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS', '*').split(','), allow_credentials=False, allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])
app.add_middleware(SecurityHeadersMiddleware)
api = APIRouter(prefix='/api')
api.include_router(auth_router)
api.include_router(voice_router)


class RoomResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    code: str
    status: str
    players: dict


class CreateRoom(BaseModel):
    difficulty: str = 'easy'


class Action(BaseModel):
    model_config = ConfigDict(extra='allow')
    type: str = Field(max_length=30)


@api.get('/health')
async def health():
    await db.command('ping')
    if not Path(ENGINE_PATH).is_file():
        raise HTTPException(503, 'Service is starting.')
    return {'status': 'ok'}


@api.get('/health/details')
async def health_details(user=Depends(current_user)):
    await db.command('ping')
    return {'status': 'ok', 'engine': 'Stockfish', 'engine_available': Path(ENGINE_PATH).is_file(), 'voice_configured': True, 'voice_transport': 'wss-pcm16', 'difficulties': STRENGTH}


@api.post('/rooms', response_model=RoomResponse)
async def create(body: CreateRoom, user=Depends(current_user)):
    count = await db.rooms.count_documents({'host_id': user['id'], 'status': 'lobby', 'created_at': {'$gt': time.time() - 3600}})
    if count >= 8:
        raise HTTPException(429, 'Please use an existing war room before creating more.')
    return await create_room(user, body.difficulty)


@api.get('/rooms')
async def rooms(user=Depends(current_user)):
    docs = await db.rooms.find({'status': 'lobby', 'created_at': {'$gt': time.time() - 86400}}, {'_id': 0, 'code': 1, 'difficulty': 1, 'players': 1, 'members': 1, 'host_id': 1, 'created_at': 1}).sort('created_at', -1).to_list(50)
    return [{'code': r['code'], 'difficulty': r['difficulty'], 'filled': len(r['players']), 'host': next((m['name'] for m in r['members'] if m['id'] == r['host_id']), 'Commander'), 'joinable': len(r['members']) < 6 or user['id'] in [m['id'] for m in r['members']], 'roles': list(r['players'])} for r in docs if all(p['state'] != 'left' for p in r['players'].values())]


@api.post('/rooms/{code}/enter', response_model=RoomResponse)
async def enter(code: str, user=Depends(current_user)):
    await rate_limit(f'enter:{user["id"]}', 30)
    return await enter_room(code.upper(), user)


@api.get('/rooms/{code}', response_model=RoomResponse)
async def state(code: str, user=Depends(current_user)):
    room = await get_room(code)
    require_access(room, user['id'])
    presence = await db.presence.find({'code': room['code'], 'seen': {'$gt': time.time() - 15}}, {'_id': 0}).to_list(20)
    online = {p['user_id'] for p in presence}
    for player in room['players'].values():
        player['connected'] = player['id'] in online and player['state'] != 'left'
    return public_state(room)


@api.post('/rooms/{code}/actions', response_model=RoomResponse)
async def act(code: str, body: Action, user=Depends(current_user)):
    await rate_limit(f'action:{user["id"]}', 180)
    return await action(code.upper(), user, body.model_dump())


@api.get('/leaderboards/{role}')
async def leaderboard(role: str):
    if role not in ROLES:
        raise HTTPException(404, 'Unknown role.')
    pipeline = [{'$unwind': '$players'}, {'$match': {'players.role': role}},
                {'$group': {'_id': '$players.user_id', 'name': {'$last': '$players.name'}, 'wins': {'$sum': '$players.won'}, 'games': {'$sum': 1}, 'captures': {'$sum': '$players.captures'}, 'moves': {'$sum': '$players.moves'}}},
                {'$sort': {'wins': -1, 'captures': -1, 'games': 1}}, {'$limit': 50},
                {'$project': {'_id': 0, 'name': 1, 'wins': 1, 'games': 1, 'captures': 1, 'moves': 1}}]
    return {'role': role, 'players': await db.results.aggregate(pipeline).to_list(50)}


@api.get('/voice-client', response_class=HTMLResponse)
async def voice_client():
    return (Path(__file__).parent / 'voice.html').read_text()


@api.websocket('/ws/{code}')
async def websocket(socket: WebSocket, code: str):
    if not await registry.admit(socket):
        return
    code = code.upper()
    user = None
    room = None
    pending = True
    try:
        raw = await asyncio.wait_for(socket.receive_text(), timeout=8)
        if len(raw) > 1024:
            raise HTTPException(400, 'Invalid connection handshake.')
        hello = json.loads(raw)
        if not isinstance(hello, dict):
            raise HTTPException(400, 'Invalid connection handshake.')
        user = await authenticate(str(hello.get('token', '')))
        room = await get_room(code)
        require_access(room, user['id'])
        connection = await registry.register(socket, user['id'], digest(str(hello.get('token', ''))), code)
        registry.pending -= 1
        pending = False
        sockets.setdefault(code, {})[socket] = user['id']
        async with room_lock(code):
            room = await get_room(code)
            player = member(room, user['id'])
            if player:
                player['connected'] = True
            await save(room)
        while True:
            raw = await socket.receive_text()
            if len(raw) > 1024 or not registry.allow_message(connection):
                raise HTTPException(429, 'Connection message limit exceeded.')
            message = json.loads(raw)
            if not isinstance(message, dict):
                raise HTTPException(400, 'Invalid connection message.')
            if message.get('type') == 'ping':
                # Revalidate revocable sessions on every heartbeat.
                await authenticate(str(hello.get('token', '')))
                room = await get_room(code)
                require_access(room, user['id'])
                await registry.send_state(socket, {'type': 'state', 'room': public_state(room)}, room)
    except (WebSocketDisconnect, HTTPException, asyncio.TimeoutError, ValueError, RuntimeError):
        with suppress(Exception):
            await socket.close(code=1008)
    finally:
        if pending:
            registry.pending = max(0, registry.pending - 1)
        await registry.remove(socket)
        sockets.get(code, {}).pop(socket, None)
        if not sockets.get(code):
            sockets.pop(code, None)
        if user and room and user['id'] not in sockets.get(code, {}).values():
            async with room_lock(code):
                room = await get_room(code)
                player = member(room, user['id'])
                if player:
                    player['connected'] = False
                    await save(room)


app.include_router(api)
static_dir = Path(__file__).parent / 'static'
static_dir.mkdir(exist_ok=True)
app.mount('/api/static', StaticFiles(directory=static_dir), name='static')