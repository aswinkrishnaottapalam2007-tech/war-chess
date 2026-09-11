import time
import asyncio
from contextlib import asynccontextmanager

import chess
import pytest
from fastapi import HTTPException

import game_service
import rules
import server


# Advanced War Chess rule coverage: approvals, timers, elimination, promotion, restarts.


def _players():
    return {
        role: {
            'id': f'u_{role}',
            'name': role.title(),
            'role': role,
            'ready': True,
            'connected': True,
            'state': 'active',
        }
        for role in rules.ROLES
    }


def _room(code='UNIT01'):
    players = _players()
    room = {
        'code': code,
        'host_id': players['king']['id'],
        'difficulty': 'easy',
        'players': players,
        'members': [{'id': p['id'], 'name': p['name']} for p in players.values()],
        'events': [],
        'chat': [],
        'created_at': time.time(),
        'updated_at': time.time(),
    }
    rules.reset_board(room)
    room.update(status='active', phase='strategy', deadline=time.time() + 60)
    return room


@asynccontextmanager
async def _noop_lock(_code):
    yield


def test_approval_required_matrix_includes_bishop_knight():
    # Bishop capture is free within first four human moves, then approval-gated.
    board_b = chess.Board('4k3/8/8/3p4/2B5/8/8/4K3 w - - 0 1')
    move_b = chess.Move.from_uci('c4d5')
    room_open = {'human_moves': 3, 'owners': {'c4': 'bishop', 'e1': 'king'}}
    room_late = {'human_moves': 4, 'owners': {'c4': 'bishop', 'e1': 'king'}}
    assert rules.approval_required(room_open, board_b, move_b, 'bishop') is False
    assert rules.approval_required(room_late, board_b, move_b, 'bishop') is True

    # Knight non-capture after opening requires approval unless lone surviving knight.
    board_k = chess.Board('4k3/8/8/8/8/5N2/8/1N2K3 w - - 0 1')
    move_k = chess.Move.from_uci('f3g5')
    room_many_knights = {'human_moves': 6, 'owners': {'f3': 'knight', 'b1': 'knight', 'e1': 'king'}}
    room_lone_knight = {'human_moves': 6, 'owners': {'f3': 'knight', 'e1': 'king'}}
    assert rules.approval_required(room_many_knights, board_k, move_k, 'knight') is True
    assert rules.approval_required(room_lone_knight, board_k, move_k, 'knight') is False


def test_action_approval_request_reject_approve_and_stale_invalidation(monkeypatch):
    room = _room('APR001')
    room['position_version'] = 5

    capture_board = chess.Board('4k3/8/8/3p4/4Q3/8/8/4K3 w - - 0 1')
    capture_move = chess.Move.from_uci('e4d5')
    executed = []

    async def _get_room(_code):
        return room

    async def _save(_room):
        return None

    def _validate(_room, _user_id, uci, position_version):
        assert position_version == room['position_version']
        assert uci == 'e4d5'
        return capture_board.copy(stack=False), capture_move, 'queen'

    def _execute(_room, board, move, actor):
        executed.append((actor, move.uci(), board.is_capture(move)))
        _room['history'].append({'san': board.san(move), 'uci': move.uci(), 'actor': actor, 'capture': True})
        _room['position_version'] += 1
        _room['approvals'] = []

    monkeypatch.setattr(game_service, 'room_lock', _noop_lock)
    monkeypatch.setattr(game_service, 'get_room', _get_room)
    monkeypatch.setattr(game_service, 'save', _save)
    monkeypatch.setattr(game_service, 'validate_move', _validate)
    monkeypatch.setattr(game_service, 'execute_move', _execute)

    queen_user = {'id': room['players']['queen']['id'], 'name': room['players']['queen']['name']}
    king_user = {'id': room['players']['king']['id'], 'name': room['players']['king']['name']}

    asyncio.run(game_service.action(room['code'], queen_user, {'type': 'move', 'uci': 'e4d5', 'position_version': 5}))
    assert len(room['approvals']) == 1
    first_request_id = room['approvals'][0]['id']

    asyncio.run(game_service.action(room['code'], king_user, {'type': 'approval', 'request_id': first_request_id, 'approve': False}))
    assert room['approvals'] == []

    asyncio.run(game_service.action(room['code'], queen_user, {'type': 'move', 'uci': 'e4d5', 'position_version': 5}))
    stale_request_id = room['approvals'][0]['id']

    room['approvals'] = []
    with pytest.raises(HTTPException) as stale:
        asyncio.run(game_service.action(room['code'], king_user, {'type': 'approval', 'request_id': stale_request_id, 'approve': True}))
    assert stale.value.status_code == 409

    asyncio.run(game_service.action(room['code'], queen_user, {'type': 'move', 'uci': 'e4d5', 'position_version': 5}))
    final_request_id = room['approvals'][0]['id']
    asyncio.run(game_service.action(room['code'], king_user, {'type': 'approval', 'request_id': final_request_id, 'approve': True}))
    assert executed == [('queen', 'e4d5', True)]


def test_timer_boundary_command_authority_and_fourth_expiry_defeat():
    room = _room('TMR001')
    room['deadline'] = time.time() - 1

    transitioned = game_service.tick_timer(room)
    assert transitioned is True
    assert room['phase'] == 'command'
    assert room['command_count'] == 1

    # Expired strategy timer should trigger only once at this boundary.
    second_tick = game_service.tick_timer(room)
    assert second_tick is False
    assert room['command_count'] == 1

    room_cmd = _room('CMD001')
    room_cmd.update(phase='command', position_version=0)
    room_cmd['owners'] = {'e2': 'pawn', 'e1': 'king'}

    with pytest.raises(HTTPException) as blocked_non_king:
        rules.validate_move(room_cmd, room_cmd['players']['pawn']['id'], 'e2e4', 0)
    assert blocked_non_king.value.status_code == 403

    board, move, owner = rules.validate_move(room_cmd, room_cmd['players']['king']['id'], 'e2e4', 0)
    assert move in board.legal_moves
    assert owner == 'pawn'

    room_defeat = _room('TMR004')
    for expected_count in (1, 2, 3):
        room_defeat.update(phase='strategy', deadline=time.time() - 1)
        assert game_service.tick_timer(room_defeat) is True
        assert room_defeat['command_count'] == expected_count
        assert room_defeat['status'] == 'active'

    room_defeat.update(phase='strategy', deadline=time.time() - 1)
    assert game_service.tick_timer(room_defeat) is True
    assert room_defeat['command_count'] == 4
    assert room_defeat['status'] == 'finished'
    assert room_defeat['result'] == 'defeat'


def test_execute_move_capture_elimination_then_spectate_and_leave(monkeypatch):
    room = _room('ELM001')
    room['owners'] = {'a1': 'rook', 'e1': 'king'}

    for role in ('queen', 'bishop', 'knight', 'pawn'):
        room['players'][role]['state'] = 'spectating'

    board = chess.Board('4k3/8/8/8/8/8/r7/R3K3 b Q - 0 1')
    move = chess.Move.from_uci('a2a1')
    rules.execute_move(room, board, move, 'Stockfish')
    assert room['players']['rook']['state'] == 'eliminated'
    room['moves'] = []

    async def _get_room(_code):
        return room

    async def _save(_room):
        return None

    monkeypatch.setattr(game_service, 'room_lock', _noop_lock)
    monkeypatch.setattr(game_service, 'get_room', _get_room)
    monkeypatch.setattr(game_service, 'save', _save)

    rook_user = {'id': room['players']['rook']['id'], 'name': room['players']['rook']['name']}
    asyncio.run(game_service.action(room['code'], rook_user, {'type': 'spectate'}))
    assert room['players']['rook']['state'] == 'spectating'

    asyncio.run(game_service.action(room['code'], rook_user, {'type': 'leave'}))
    assert room['players']['rook']['state'] == 'left'


def test_promotion_matrix_qrbn_pending_and_pawn_ownership():
    role_by_suffix = {'q': 'queen', 'r': 'rook', 'b': 'bishop', 'n': 'knight'}

    for suffix, target_role in role_by_suffix.items():
        room = _room(f'PRM_{suffix.upper()}')
        room['owners'] = {'g7': 'pawn', 'e1': 'king'}
        room['players'][target_role]['state'] = 'spectating'
        board = chess.Board('4k3/6P1/8/8/8/8/8/4K3 w - - 0 1')

        rules.execute_move(room, board, chess.Move.from_uci(f'g7g8{suffix}'), 'pawn')

        assert room['owners']['g8'] == 'pawn'
        assert room['promotion']['role'] == target_role
        assert room['promotion']['square'] == 'g8'
        assert room['phase'] == 'promotion'


def test_promotion_transfer_refusal_keep_and_timeout_default(monkeypatch):
    async def _save(_room):
        return None

    monkeypatch.setattr(game_service, 'room_lock', _noop_lock)
    monkeypatch.setattr(game_service, 'save', _save)

    room_transfer = _room('PRM_TR')
    room_transfer.update(phase='promotion', promotion={'square': 'g8', 'role': 'queen', 'expires': time.time() + 30})
    room_transfer['owners'] = {'g8': 'pawn', 'e1': 'king'}
    room_transfer['players']['queen']['state'] = 'spectating'

    async def _get_room_transfer(_code):
        return room_transfer

    monkeypatch.setattr(game_service, 'get_room', _get_room_transfer)
    pawn_user = {'id': room_transfer['players']['pawn']['id'], 'name': room_transfer['players']['pawn']['name']}
    asyncio.run(game_service.action(room_transfer['code'], pawn_user, {'type': 'promotion', 'transfer': True}))
    assert room_transfer['owners']['g8'] == 'queen'
    assert room_transfer['players']['queen']['state'] == 'active'
    assert room_transfer['promotion'] is None

    room_left = _room('PRM_LF')
    room_left.update(phase='promotion', promotion={'square': 'g8', 'role': 'queen', 'expires': time.time() + 30})
    room_left['owners'] = {'g8': 'pawn', 'e1': 'king'}
    room_left['players']['queen']['state'] = 'left'

    async def _get_room_left(_code):
        return room_left

    monkeypatch.setattr(game_service, 'get_room', _get_room_left)
    with pytest.raises(HTTPException) as left_reject:
        asyncio.run(game_service.action(room_left['code'], {'id': room_left['players']['pawn']['id'], 'name': 'Pawn'}, {'type': 'promotion', 'transfer': True}))
    assert left_reject.value.status_code == 409

    room_keep = _room('PRM_KP')
    room_keep.update(phase='promotion', promotion={'square': 'g8', 'role': 'queen', 'expires': time.time() + 30})
    room_keep['owners'] = {'g8': 'pawn', 'e1': 'king'}
    room_keep['players']['queen']['state'] = 'spectating'

    async def _get_room_keep(_code):
        return room_keep

    monkeypatch.setattr(game_service, 'get_room', _get_room_keep)
    asyncio.run(game_service.action(room_keep['code'], {'id': room_keep['players']['pawn']['id'], 'name': 'Pawn'}, {'type': 'promotion', 'transfer': False}))
    assert room_keep['owners']['g8'] == 'pawn'
    assert room_keep['promotion'] is None

    room_timeout = _room('PRM_TO')
    room_timeout.update(phase='promotion', promotion={'square': 'g8', 'role': 'queen', 'expires': time.time() - 1})
    room_timeout['owners'] = {'g8': 'pawn', 'e1': 'king'}
    assert game_service.tick_timer(room_timeout) is True
    assert room_timeout['promotion'] is None
    assert room_timeout['owners']['g8'] == 'pawn'


def test_after_position_checkmate_stalemate_draw_notice_and_canonical_history():
    # Canonical board state is reconstructed from move history, not arbitrary stored fen.
    reconstructed = rules.board_for({'moves': ['e2e4'], 'fen': '8/8/8/8/8/8/8/8 w - - 0 1'})
    assert reconstructed.fen().startswith('rnbqkbnr/pppppppp/8/8/4P3')

    room_mate = _room('CHK001')
    board_mate = chess.Board('7k/6Q1/6K1/8/8/8/8/8 b - - 0 1')
    rules.after_position(room_mate, board_mate)
    assert room_mate['status'] == 'finished'
    assert room_mate['result'] == 'victory'

    room_stalemate = _room('STL001')
    board_stalemate = chess.Board('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1')
    rules.after_position(room_stalemate, board_stalemate)
    assert room_stalemate['status'] == 'active'
    assert room_stalemate['phase'] == 'stalled'
    assert 'Stalemate' in room_stalemate['draw_notice']

    room_insufficient = _room('DRW001')
    board_insufficient = chess.Board('8/8/8/8/8/8/8/K1k5 w - - 0 1')
    rules.after_position(room_insufficient, board_insufficient)
    assert room_insufficient['status'] == 'active'
    assert room_insufficient['phase'] == 'strategy'
    assert room_insufficient['draw_notice'] == 'A standard draw condition is present. War Chess continues.'


def test_execute_move_en_passant_and_castling_rook_ownership():
    # En passant ownership transfer.
    room_ep = _room('EP001')
    room_ep['owners'] = {'e5': 'pawn', 'e1': 'king', 'h1': 'rook', 'a1': 'rook'}
    board_ep = chess.Board()
    for uci in ('e2e4', 'a7a6', 'e4e5', 'd7d5'):
        board_ep.push_uci(uci)
    rules.execute_move(room_ep, board_ep, chess.Move.from_uci('e5d6'), 'pawn')
    assert room_ep['owners'].get('d6') == 'pawn'
    assert 'e5' not in room_ep['owners']

    # Kingside castling should transfer h1 rook ownership to f1.
    room_ks = _room('CSK01')
    room_ks['owners'] = {'e1': 'king', 'h1': 'rook', 'a1': 'rook'}
    board_ks = chess.Board()
    for uci in ('e2e3', 'a7a6', 'g1f3', 'a6a5', 'f1e2', 'a5a4'):
        board_ks.push_uci(uci)
    rules.execute_move(room_ks, board_ks, chess.Move.from_uci('e1g1'), 'king')
    assert room_ks['owners'].get('f1') == 'rook'

    # Queenside castling should transfer a1 rook ownership to d1.
    room_qs = _room('CSQ01')
    room_qs['owners'] = {'e1': 'king', 'a1': 'rook', 'h1': 'rook'}
    board_qs = chess.Board()
    for uci in ('b1c3', 'a7a6', 'd2d4', 'a6a5', 'c1d2', 'a5a4', 'd1c1', 'a4a3'):
        board_qs.push_uci(uci)
    rules.execute_move(room_qs, board_qs, chess.Move.from_uci('e1c1'), 'king')
    assert room_qs['owners'].get('d1') == 'rook'


def test_restart_votes_three_not_enough_four_resets_lobby(monkeypatch):
    room = _room('RST001')
    room.update(status='active', phase='strategy')

    async def _get_room(_code):
        return room

    async def _save(_room):
        return None

    monkeypatch.setattr(game_service, 'room_lock', _noop_lock)
    monkeypatch.setattr(game_service, 'get_room', _get_room)
    monkeypatch.setattr(game_service, 'save', _save)

    for role in ('king', 'queen', 'rook'):
        asyncio.run(game_service.action(room['code'], {'id': room['players'][role]['id'], 'name': role}, {'type': 'restart', 'yes': True}))

    assert room['status'] == 'active'
    assert room['restart_requested'] is True
    assert sum(v is True for v in room['votes'].values()) == 3

    asyncio.run(game_service.action(room['code'], {'id': room['players']['bishop']['id'], 'name': 'bishop'}, {'type': 'restart', 'yes': True}))

    assert room['status'] == 'lobby'
    assert room['phase'] == 'lobby'
    assert len(room['players']) == 6
    assert all(p['state'] == 'active' for p in room['players'].values())
    assert all(p['ready'] is False for p in room['players'].values())


def test_finished_result_durable_once_and_per_role_leaderboard(monkeypatch):
    class _FakeRooms:
        def __init__(self):
            self.replacements = 0

        async def replace_one(self, _query, _doc):
            self.replacements += 1

    class _Cursor:
        def __init__(self, rows):
            self.rows = rows

        async def to_list(self, _limit):
            return self.rows

    class _FakeResults:
        def __init__(self):
            self.docs = {}

        async def update_one(self, query, update, upsert=False):
            assert upsert is True
            rid = query['round_id']
            if rid not in self.docs:
                self.docs[rid] = update['$setOnInsert']

        def aggregate(self, pipeline):
            role = pipeline[1]['$match']['players.role']
            grouped = {}
            for doc in self.docs.values():
                for p in doc['players']:
                    if p['role'] != role:
                        continue
                    row = grouped.setdefault(
                        p['user_id'],
                        {'user_id': p['user_id'], 'name': p['name'], 'wins': 0, 'games': 0, 'captures': 0, 'moves': 0},
                    )
                    row['wins'] += p['won']
                    row['games'] += 1
                    row['captures'] += p['captures']
                    row['moves'] += p['moves']
            rows = sorted(grouped.values(), key=lambda r: (-r['wins'], -r['captures'], r['games']))[:50]
            return _Cursor(rows)

    class _FakeDB:
        def __init__(self):
            self.rooms = _FakeRooms()
            self.results = _FakeResults()

    fake_db = _FakeDB()

    async def _broadcast(_room):
        return None

    monkeypatch.setattr(game_service, 'db', fake_db)
    monkeypatch.setattr(server, 'db', fake_db)
    monkeypatch.setattr(game_service, 'broadcast', _broadcast)

    room = _room('RES001')
    room.update(status='finished', phase='finished', result='victory', round_id='round-1')
    room['history'] = [
        {'actor': 'king', 'capture': False, 'san': 'e4', 'uci': 'e2e4'},
        {'actor': 'queen', 'capture': True, 'san': 'Qxd5', 'uci': 'e4d5'},
        {'actor': 'king', 'capture': False, 'san': 'Nf3', 'uci': 'g1f3'},
    ]

    asyncio.run(game_service.save(room))
    asyncio.run(game_service.save(room))

    assert len(fake_db.results.docs) == 1
    stored = fake_db.results.docs['round-1']
    assert len(stored['players']) == 6
    king_row = next(r for r in stored['players'] if r['role'] == 'king')
    queen_row = next(r for r in stored['players'] if r['role'] == 'queen')
    assert king_row['moves'] == 2
    assert queen_row['captures'] == 1

    king_board = asyncio.run(server.leaderboard('king'))
    assert king_board['role'] == 'king'
    assert king_board['players'][0]['user_id'] == room['players']['king']['id']
    assert king_board['players'][0]['games'] == 1
