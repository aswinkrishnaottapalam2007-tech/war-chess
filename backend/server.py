import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
from pathlib import Path
from fastapi import FastAPI, APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from database import db, client
from auth import router as auth_router, current_user, authenticate
from game_service import create_room, enter_room, get_room, require_access, action, sockets, clock_loop, room_lock, save
from rules import ROLES, member, public_state
from engine import STRENGTH, ENGINE_PATH

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
    task = asyncio.create_task(clock_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    client.close()


app = FastAPI(title='WAR CHESS Authoritative API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS', '*').split(','), allow_credentials=False, allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])
api = APIRouter(prefix='/api')
api.include_router(auth_router)


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
    return {'status': 'ok', 'engine': 'Stockfish', 'engine_available': Path(ENGINE_PATH).exists(), 'voice_configured': all(os.getenv(k) for k in ['LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET']), 'difficulties': STRENGTH}


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
    return await action(code.upper(), user, body.model_dump())


@api.get('/leaderboards/{role}')
async def leaderboard(role: str):
    if role not in ROLES:
        raise HTTPException(404, 'Unknown role.')
    pipeline = [{'$unwind': '$players'}, {'$match': {'players.role': role}},
                {'$group': {'_id': '$players.user_id', 'name': {'$last': '$players.name'}, 'wins': {'$sum': '$players.won'}, 'games': {'$sum': 1}, 'captures': {'$sum': '$players.captures'}, 'moves': {'$sum': '$players.moves'}}},
                {'$sort': {'wins': -1, 'captures': -1, 'games': 1}}, {'$limit': 50},
                {'$project': {'_id': 0, 'user_id': '$_id', 'name': 1, 'wins': 1, 'games': 1, 'captures': 1, 'moves': 1}}]
    return {'role': role, 'players': await db.results.aggregate(pipeline).to_list(50)}


@api.post('/rooms/{code}/voice')
async def voice(code: str, user=Depends(current_user)):
    room = await get_room(code)
    require_access(room, user['id'])
    if not member(room, user['id']):
        raise HTTPException(403, 'Choose a role before joining team voice.')
    if not all(os.getenv(k) for k in ['LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET']):
        raise HTTPException(503, 'Live voice is awaiting LiveKit project credentials. Team text chat is available now.')
    from livekit import api as lk
    token = (lk.AccessToken(os.environ['LIVEKIT_API_KEY'], os.environ['LIVEKIT_API_SECRET'])
             .with_identity(user['id']).with_name(user['name']).with_ttl(timedelta(minutes=10))
             .with_grants(lk.VideoGrants(room_join=True, room=room['voice_room'], can_publish=True,
                                       can_publish_sources=['microphone'], can_subscribe=True, can_publish_data=False)))
    return {'server_url': os.environ['LIVEKIT_URL'], 'participant_token': token.to_jwt()}


@api.get('/voice-client', response_class=HTMLResponse)
async def voice_client():
    return (Path(__file__).parent / 'voice.html').read_text()


@api.websocket('/ws/{code}')
async def websocket(socket: WebSocket, code: str):
    await socket.accept()
    code = code.upper()
    user = None
    try:
        hello = await asyncio.wait_for(socket.receive_json(), timeout=10)
        user = await authenticate(str(hello.get('token', '')))
        room = await get_room(code)
        require_access(room, user['id'])
        sockets.setdefault(code, {})[socket] = user['id']
        async with room_lock(code):
            room = await get_room(code)
            player = member(room, user['id'])
            if player:
                player['connected'] = True
            await save(room)
        while True:
            message = await socket.receive_json()
            if message.get('type') == 'ping':
                # Revalidate revocable sessions on every heartbeat.
                await authenticate(str(hello.get('token', '')))
                room = await get_room(code)
                require_access(room, user['id'])
                await socket.send_json({'type': 'state', 'room': public_state(room)})
    except (WebSocketDisconnect, HTTPException, asyncio.TimeoutError, ValueError):
        with suppress(Exception):
            await socket.close(code=1008)
    finally:
        sockets.get(code, {}).pop(socket, None)
        if user and user['id'] not in sockets.get(code, {}).values():
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