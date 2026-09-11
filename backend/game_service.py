import asyncio
import logging
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from database import db
from engine import choose_move
from realtime import registry
from rules import (ROLES, DIFFICULTIES, announce, member, board_for, validate_move, approval_required,
                   execute_move, reset_board, public_state, after_position, eliminate, finish_game)

logger = logging.getLogger(__name__)
sockets = {}
ai_jobs = set()


@asynccontextmanager
async def room_lock(code):
    """Mongo-backed lease: mutations serialize even when more than one worker runs."""
    token = secrets.token_hex(16)
    acquired = False
    for _ in range(100):
        now = time.time()
        try:
            doc = await db.room_locks.find_one_and_update(
                {'_id': code, '$or': [{'until': {'$lt': now}}, {'owner': token}]},
                {'$set': {'owner': token, 'until': now + 15}}, upsert=True, return_document=True)
            acquired = bool(doc and doc['owner'] == token)
        except DuplicateKeyError:
            acquired = False
        if acquired:
            break
        await asyncio.sleep(0.04)
    if not acquired:
        raise HTTPException(503, 'Room is busy. Please try again.')
    try:
        yield
    finally:
        await db.room_locks.delete_one({'_id': code, 'owner': token})


async def get_room(code):
    room = await db.rooms.find_one({'code': code.upper()}, {'_id': 0})
    if not room:
        raise HTTPException(404, 'War room not found. Check the six-letter code.')
    return room


def require_access(room, user_id):
    if user_id not in [m['id'] for m in room['members']]:
        raise HTTPException(403, 'Join this war room first.')
    player = member(room, user_id)
    if player and player['state'] == 'left':
        raise HTTPException(403, 'You left this match. Join a new war room.')


async def broadcast(room):
    payload = {'type': 'state', 'room': public_state(room)}
    for socket in list(sockets.get(room['code'], {}).keys()):
        try:
            if not await registry.send_state(socket, payload, room):
                sockets.get(room['code'], {}).pop(socket, None)
        except Exception:
            sockets.get(room['code'], {}).pop(socket, None)


async def save(room):
    room['revision'] = room.get('revision', 0) + 1
    room['updated_at'] = time.time()
    await db.rooms.replace_one({'code': room['code']}, room.copy())
    if room['status'] == 'finished':
        rows = []
        for role, player in room['players'].items():
            if player['id'].startswith('deleted-'):
                continue
            rows.append({'role': role, 'user_id': player['id'], 'name': player['name'],
                         'won': int(room['result'] == 'victory'), 'moves': sum(1 for h in room['history'] if h['actor'] == role),
                         'captures': sum(1 for h in room['history'] if h['actor'] == role and h['capture'])})
        await db.results.update_one({'round_id': room['round_id']}, {'$setOnInsert': {'round_id': room['round_id'], 'result': room['result'], 'players': rows, 'ended_at': time.time()}}, upsert=True)
    await broadcast(room)


async def create_room(user, difficulty):
    if difficulty not in DIFFICULTIES:
        raise HTTPException(400, 'Choose a valid difficulty.')
    room = {'code': ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(6)), 'host_id': user['id'],
            'difficulty': difficulty, 'players': {}, 'members': [{'id': user['id'], 'name': user['name']}],
            'chat': [], 'events': [], 'revision': 0, 'created_at': time.time(), 'updated_at': time.time(), 'voice_room': 'war-' + secrets.token_hex(18)}
    reset_board(room)
    announce(room, 'created', f'{user["name"]} opened the war room.')
    await db.rooms.insert_one(room.copy())
    await db.users.update_one({'id': user['id']}, {'$addToSet': {'room_codes': room['code']}})
    return public_state(room)


async def enter_room(code, user):
    async with room_lock(code):
        room = await get_room(code)
        if user['id'] not in [m['id'] for m in room['members']]:
            if room['status'] != 'lobby' or len(room['members']) >= 6:
                raise HTTPException(409, 'This room is full or already in battle.')
            room['members'].append({'id': user['id'], 'name': user['name']})
            announce(room, 'joined', f'{user["name"]} joined the war room.')
            await save(room)
        require_access(room, user['id'])
        await db.users.update_one({'id': user['id']}, {'$addToSet': {'room_codes': room['code']}})
        return public_state(room)


def start_if_ready(room):
    if len(room['players']) == 6 and all(p['ready'] and p['state'] == 'active' for p in room['players'].values()):
        room.update(status='active', phase='strategy', deadline=time.time() + 60)
        announce(room, 'match_started', 'Six commanders. One kingdom. The battle begins.')


def tick_timer(room):
    if room['status'] != 'active':
        return False
    if room['phase'] == 'strategy' and room.get('deadline') and time.time() >= room['deadline']:
        room['command_count'] += 1
        room['approvals'] = []
        if room['command_count'] > 3:
            finish_game(room, 'defeat', 'Four unanswered strategy periods. The entire team is eliminated.')
        else:
            room.update(phase='command', deadline=None)
            announce(room, 'king_command', 'NO COMMAND RECEIVED. Moving authority transferred to King.')
        return True
    if room['phase'] == 'promotion' and room['promotion']['expires'] <= time.time():
        room['promotion'] = None
        after_position(room, board_for(room))
        announce(room, 'promotion_kept', 'Pawn retained control of the promoted piece.')
        return True
    return False


async def action(code, user, data):
    async with room_lock(code):
        room = await get_room(code)
        require_access(room, user['id'])
        if tick_timer(room):
            await save(room)
        player = member(room, user['id'])
        kind = data['type']
        if kind == 'role':
            role = data.get('role')
            if room['status'] != 'lobby' or player:
                raise HTTPException(409, 'Your role is locked for this match.')
            if role not in ROLES or role in room['players']:
                raise HTTPException(409, 'This role is unavailable.')
            room['players'][role] = {'id': user['id'], 'name': user['name'], 'role': role, 'ready': False, 'connected': True, 'state': 'active'}
            announce(room, 'role_locked', f'{user["name"]} is the {role.title()}.')
        elif kind == 'ready':
            if not player or room['status'] != 'lobby':
                raise HTTPException(400, 'Choose your role before readying up.')
            player['ready'] = bool(data.get('ready', True))
            start_if_ready(room)
        elif kind == 'difficulty':
            if room['host_id'] != user['id'] or room['status'] != 'lobby' or data.get('difficulty') not in DIFFICULTIES:
                raise HTTPException(403, 'Only the host can set difficulty before the match.')
            room['difficulty'] = data['difficulty']
        elif kind == 'move':
            board, move, owner = validate_move(room, user['id'], data.get('uci', ''), data.get('position_version'))
            if room['phase'] != 'command' and approval_required(room, board, move, owner):
                room['approvals'] = [a for a in room['approvals'] if a['user_id'] != user['id']]
                room['approvals'].append({'id': str(uuid.uuid4()), 'user_id': user['id'], 'role': player['role'], 'uci': move.uci(), 'san': board.san(move), 'position_version': room['position_version'], 'capture': board.is_capture(move)})
                announce(room, 'approval_requested', f'{player["role"].title()} requests {board.san(move)}. Awaiting King approval.')
            else:
                execute_move(room, board, move, player['role'])
        elif kind == 'approval':
            if not player or player['role'] != 'king' or player['state'] != 'active' or room['phase'] != 'strategy':
                raise HTTPException(403, 'Only the King can authorize a strategy move.')
            proposal = next((a for a in room['approvals'] if a['id'] == data.get('request_id')), None)
            if not proposal:
                raise HTTPException(409, 'That request has expired.')
            room['approvals'].remove(proposal)
            if data.get('approve') is True:
                board, move, _ = validate_move(room, proposal['user_id'], proposal['uci'], proposal['position_version'])
                announce(room, 'approval_granted', f'King approved {proposal["san"]}.')
                execute_move(room, board, move, proposal['role'])
            else:
                announce(room, 'approval_rejected', f'King rejected {proposal["san"]}. Choose another move.')
        elif kind == 'chat':
            text = str(data.get('text', '')).strip()
            if not text or len(text) > 500:
                raise HTTPException(400, 'Messages must contain 1–500 characters.')
            recent = [m for m in room['chat'] if m['user_id'] == user['id'] and m['at'] > time.time() - 10]
            if len(recent) >= 8:
                raise HTTPException(429, 'Give your team a moment to respond.')
            room['chat'] = (room['chat'] + [{'id': str(uuid.uuid4()), 'user_id': user['id'], 'name': user['name'], 'role': player['role'] if player else None, 'text': text, 'at': time.time()}])[-150:]
        elif kind == 'spectate':
            if not player or player['state'] != 'eliminated' or room['status'] != 'active':
                raise HTTPException(400, 'Spectating is available after elimination.')
            player['state'] = 'spectating'
            announce(room, 'spectating', f'{player["name"]} is spectating and eligible to return.')
        elif kind == 'promotion':
            if not player or player['role'] != 'pawn' or room['phase'] != 'promotion':
                raise HTTPException(403, 'Only Pawn can choose promotion ownership.')
            promotion = room['promotion']
            target = room['players'][promotion['role']]
            if data.get('transfer') is True:
                if target['state'] != 'spectating':
                    raise HTTPException(409, 'That commander is no longer spectating.')
                room['owners'][promotion['square']] = promotion['role']
                target['state'] = 'active'
                announce(room, 'returned', f'{promotion["role"].title()} commander has returned.')
            else:
                announce(room, 'promotion_kept', 'Pawn retained control of the promoted piece.')
            room['promotion'] = None
            eliminate(room)
            after_position(room, board_for(room))
        elif kind == 'restart':
            if not player or player['state'] == 'left' or room['status'] == 'lobby':
                raise HTTPException(403, 'Only match commanders may vote.')
            room['restart_requested'] = True
            room['votes'][user['id']] = bool(data.get('yes'))
            yes_count = sum(v is True for v in room['votes'].values())
            announce(room, 'restart_vote', f'{player["name"]} voted {"yes" if data.get("yes") else "no"}. {yes_count}/4 approvals.')
            if yes_count >= 4:
                reset_board(room)
                room['members'] = [m for m in room['members'] if m['id'] in [p['id'] for p in room['players'].values()]]
                announce(room, 'restart_accepted', 'Restart accepted. Ready up for a new battle.')
        elif kind == 'leave':
            if player:
                player['state'] = 'left'
                player['connected'] = False
                player['ready'] = False
            if room['status'] == 'lobby':
                # Locked slots remain locked; create a new room if a commander abandons the lobby.
                if not player:
                    room['members'] = [m for m in room['members'] if m['id'] != user['id']]
            announce(room, 'left', f'{user["name"]} left the match and cannot be revived.')
        else:
            raise HTTPException(400, 'Unknown action.')
        await save(room)
        return public_state(room)


async def run_ai(code, round_id, position_version):
    key = (code, round_id, position_version)
    try:
        room = await get_room(code)
        move = await choose_move(board_for(room), room['difficulty'])
        async with room_lock(code):
            room = await get_room(code)
            if room['round_id'] == round_id and room['position_version'] == position_version and room['phase'] == 'ai':
                board = board_for(room)
                if move in board.legal_moves:
                    execute_move(room, board, move, 'Stockfish')
                    room['engine_error'] = None
                    await save(room)
    except Exception:
        logger.exception('Engine job failed for room %s', code)
        async with room_lock(code):
            room = await get_room(code)
            if room['phase'] == 'ai' and room['position_version'] == position_version:
                room['engine_error'] = 'The chess engine is temporarily unavailable. Retrying automatically.'
                room['engine_retry_at'] = time.time() + 10
                await save(room)
    finally:
        ai_jobs.discard(key)


async def clock_loop():
    while True:
        try:
            rooms = await db.rooms.find({'status': 'active'}, {'_id': 0}).to_list(1000)
            for snapshot in rooms:
                code = snapshot['code']
                if snapshot['phase'] in ('strategy', 'promotion'):
                    async with room_lock(code):
                        room = await get_room(code)
                        if tick_timer(room):
                            await save(room)
                if snapshot['phase'] == 'ai' and snapshot.get('engine_retry_at', 0) < time.time():
                    key = (code, snapshot['round_id'], snapshot['position_version'])
                    if key not in ai_jobs:
                        ai_jobs.add(key)
                        asyncio.create_task(run_ai(*key))
            # Durable presence heartbeats work across API workers.
            for code in list(sockets):
                for uid in set(sockets[code].values()):
                    await db.presence.update_one({'code': code, 'user_id': uid}, {'$set': {'seen': time.time()}}, upsert=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Room clock recovered from an error')
        await asyncio.sleep(1)