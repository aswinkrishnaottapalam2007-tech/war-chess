import asyncio
import uuid
import logging
from database import db
from realtime import registry


async def cleanup_account(user_id):
    from game_service import room_lock, get_room, save
    await db.sessions.delete_many({'user_id': user_id})
    await db.voice_tickets.delete_many({'user_id': user_id})
    await registry.revoke(user_id=user_id)
    account = await db.users.find_one({'id': user_id}, {'_id': 0, 'room_codes': 1})
    visited = (account or {}).get('room_codes', [])
    rooms = await db.rooms.find({'$or': [{'members.id': user_id}, {'chat.user_id': user_id}, {'host_id': user_id}, {'code': {'$in': visited}}]}, {'_id': 0, 'code': 1}).to_list(10000)
    for item in rooms:
        async with room_lock(item['code']):
            room = await get_room(item['code'])
            room['members'] = [m for m in room['members'] if m['id'] != user_id]
            room['chat'] = [m for m in room['chat'] if m['user_id'] != user_id]
            room['events'] = []
            room['votes'].pop(user_id, None)
            room['approvals'] = [a for a in room['approvals'] if a['user_id'] != user_id]
            for player in room['players'].values():
                if player['id'] == user_id:
                    player.update(id='deleted-' + uuid.uuid4().hex, name='Deleted commander', state='left', ready=False, connected=False)
            if room['host_id'] == user_id:
                room['host_id'] = next((m['id'] for m in room['members']), '')
            await save(room)
    await db.results.update_many({}, {'$pull': {'players': {'user_id': user_id}}})
    await db.presence.delete_many({'user_id': user_id})
    await db.socket_leases.delete_many({'user_id': user_id})
    await db.users.delete_one({'id': user_id, 'deleting': True})


async def cleanup_loop():
    while True:
        try:
            pending = await db.users.find({'deleting': True}, {'_id': 0, 'id': 1}).to_list(100)
            for user in pending:
                try:
                    await cleanup_account(user['id'])
                except Exception:
                    logging.getLogger(__name__).warning('Account cleanup deferred; durable request will retry.', exc_info=True)
                    continue  # Durable deleting flag keeps the job eligible for retry.
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(15)