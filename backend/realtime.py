"""Revocable, capacity-limited realtime connections. Never retain raw tokens."""
import asyncio
import os
import time
import uuid
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from database import db

WORKER_ID = uuid.uuid4().hex
MAX_CONNECTIONS = 400
logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc)


def member_allowed(room, user_id):
    if not room or user_id not in [m['id'] for m in room.get('members', [])]:
        return False
    player = next((p for p in room['players'].values() if p['id'] == user_id), None)
    return not player or player['state'] != 'left'


def origin_allowed(socket):
    # Fetch Metadata is browser-controlled and remains useful when an upstream
    # reverse proxy normalizes Origin to its own host. Native clients omit it.
    if socket.headers.get('sec-fetch-site') == 'cross-site':
        return False
    origin = socket.headers.get('origin')
    if not origin:
        return True  # Native clients have no browser origin; authentication remains mandatory.
    parsed = urlparse(origin)
    host = socket.headers.get('host', '')
    if parsed.netloc == host and parsed.scheme in ('http', 'https'):
        return True
    configured = (os.getenv('PUBLIC_APP_ORIGINS', '') + ',' + os.getenv('APP_URL', '')).split(',')
    return origin.rstrip('/') in [v.strip().rstrip('/') for v in configured if v.strip()]


async def rate_limit(key, limit, seconds=60):
    stamp = now()
    bucket = f'{key}:{int(stamp.timestamp()) // seconds}'
    value = await db.api_limits.find_one_and_update(
        {'key': bucket}, {'$inc': {'count': 1}, '$set': {'expires_at': stamp + timedelta(seconds=seconds * 2)}},
        upsert=True, return_document=True, projection={'_id': 0})
    if value['count'] > limit:
        raise HTTPException(429, 'Too many requests. Please pause and try again.')


@dataclass
class Connection:
    socket: object
    user_id: str
    session_hash: str
    room_code: str
    kind: str
    lease: str
    owner: str
    active: bool = True
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    window: float = field(default_factory=time.monotonic)
    events: int = 0


class Registry:
    def __init__(self):
        self.live = {}
        self.pending = 0

    async def admit(self, socket):
        allowed = origin_allowed(socket)
        logger.debug('Realtime admission path=%s origin=%r host=%r allowed=%s', socket.url.path, socket.headers.get('origin'), socket.headers.get('host'), allowed)
        if not allowed or self.pending >= 24 or len(self.live) + self.pending >= MAX_CONNECTIONS:
            await socket.close(code=1008)
            return False
        self.pending += 1
        await socket.accept()
        return True

    async def register(self, socket, user_id, session_hash, room_code, kind='state'):
        owner = uuid.uuid4().hex
        lease = None
        for slot in range(1 if kind == 'voice' else 3):
            key = f'{user_id}:{kind}:{slot}'
            try:
                result = await db.socket_leases.find_one_and_update(
                    {'_id': key, 'expires_at': {'$lte': now()}},
                    {'$set': {'owner': owner, 'worker': WORKER_ID, 'user_id': user_id, 'expires_at': now() + timedelta(seconds=15)}},
                    upsert=True, return_document=True)
                if result.get('owner') == owner:
                    lease = key
                    break
            except DuplicateKeyError:
                continue
        if not lease:
            raise HTTPException(429, 'Connection limit reached. Close another game window or voice session.')
        connection = Connection(socket, user_id, session_hash, room_code, kind, lease, owner)
        self.live[socket] = connection
        if not await self.authorized(connection):
            await self.close(connection)
            raise HTTPException(401, 'Session expired or room access ended.')
        return connection

    async def authorized(self, connection, room=None):
        if not connection.active:
            return False
        session = await db.sessions.find_one({'token_hash': connection.session_hash, 'user_id': connection.user_id, 'expires_at': {'$gt': now()}}, {'_id': 0, 'user_id': 1})
        if not session:
            return False
        account = await db.users.find_one({'id': connection.user_id, 'deleting': {'$ne': True}}, {'_id': 0, 'id': 1})
        if not account:
            return False
        if room is None:
            room = await db.rooms.find_one({'code': connection.room_code}, {'_id': 0, 'players': 1, 'members': 1})
        return member_allowed(room, connection.user_id)

    async def close(self, connection, code=4001):
        connection.active = False
        self.live.pop(connection.socket, None)
        with suppress(Exception):
            await asyncio.wait_for(connection.socket.close(code=code), 1)
        with suppress(Exception):
            await db.socket_leases.delete_one({'_id': connection.lease, 'owner': connection.owner})

    async def remove(self, socket):
        connection = self.live.pop(socket, None)
        if connection:
            connection.active = False
            with suppress(Exception):
                await db.socket_leases.delete_one({'_id': connection.lease, 'owner': connection.owner})

    async def revoke(self, session_hash=None, user_id=None):
        targets = [c for c in list(self.live.values()) if (session_hash and c.session_hash == session_hash) or (user_id and c.user_id == user_id)]
        await asyncio.gather(*(self.close(c) for c in targets), return_exceptions=True)

    async def send_state(self, socket, payload, room):
        payload = {**payload, 'realtime_version': 2}
        connection = self.live.get(socket)
        if not connection or not await self.authorized(connection, room):
            if connection:
                await self.close(connection)
            return False
        try:
            async with connection.send_lock:
                if connection.active:
                    await asyncio.wait_for(socket.send_json(payload), 2)
                    return True
        except Exception:
            await self.close(connection)
        return False

    def allow_message(self, connection, limit=30):
        current = time.monotonic()
        if current - connection.window > 10:
            connection.events = 0
            connection.window = current
        connection.events += 1
        return connection.events <= limit

    async def sweep(self):
        while True:
            for connection in list(self.live.values()):
                try:
                    if not await self.authorized(connection):
                        await self.close(connection)
                    else:
                        renewed = await db.socket_leases.update_one({'_id': connection.lease, 'owner': connection.owner}, {'$set': {'expires_at': now() + timedelta(seconds=15)}})
                        if not renewed.matched_count:
                            await self.close(connection)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    await self.close(connection)
            await asyncio.sleep(2)


registry = Registry()