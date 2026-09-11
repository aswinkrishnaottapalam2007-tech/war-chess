"""Pure War Chess rules. Board legality is delegated to python-chess."""
import time
import uuid
import chess
from fastapi import HTTPException

ROLES = ['king', 'queen', 'rook', 'bishop', 'knight', 'pawn']
DIFFICULTIES = ['easy', 'hard', 'extreme', 'regret']
TYPE_ROLE = {chess.KING: 'king', chess.QUEEN: 'queen', chess.ROOK: 'rook', chess.BISHOP: 'bishop', chess.KNIGHT: 'knight', chess.PAWN: 'pawn'}


def initial_owners():
    board = chess.Board()
    return {chess.square_name(sq): TYPE_ROLE[p.piece_type] for sq, p in board.piece_map().items() if p.color == chess.WHITE}


def announce(room, kind, message, **data):
    room['events'] = (room.get('events', []) + [{'id': str(uuid.uuid4()), 'type': kind, 'message': message, 'at': time.time(), **data}])[-80:]


def member(room, user_id):
    return next((p for p in room['players'].values() if p['id'] == user_id), None)


def board_for(room):
    board = chess.Board()
    for uci in room.get('moves', []):
        board.push_uci(uci)
    return board


def approval_required(room, board, move, role):
    if role in ('pawn', 'king'):
        return False
    capture = board.is_capture(move)
    if role == 'queen':
        return capture
    if room['human_moves'] < 4:
        return False
    if capture:
        return True
    count = sum(1 for sq, owner in room['owners'].items() if owner == role and board.piece_at(chess.parse_square(sq)))
    return count != 1


def validate_move(room, user_id, uci, position_version):
    player = member(room, user_id)
    if room['status'] != 'active' or room['phase'] not in ('strategy', 'command'):
        raise HTTPException(409, 'Wait for the next human-team turn.')
    if not player or player['state'] != 'active':
        raise HTTPException(403, 'Only an active commander can move.')
    if position_version != room['position_version']:
        raise HTTPException(409, 'The board changed. Please choose your move again.')
    board = board_for(room)
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        raise HTTPException(400, 'Invalid move format.')
    if move not in board.legal_moves:
        raise HTTPException(400, 'That move is not legal.')
    owner = room['owners'].get(chess.square_name(move.from_square))
    if room['phase'] == 'command':
        if player['role'] != 'king':
            raise HTTPException(403, 'Moving authority has transferred to the King.')
    elif owner != player['role']:
        raise HTTPException(403, 'You can only move pieces under your control.')
    return board, move, owner


def finish_game(room, result, reason):
    room.update(status='finished', phase='finished', result=result, result_reason=reason, deadline=None, approvals=[])
    if result == 'defeat':
        for player in room['players'].values():
            if player['state'] != 'left':
                player['state'] = 'eliminated'
    announce(room, 'game_end', reason)


def eliminate(room):
    for role, player in room['players'].items():
        if player['state'] == 'active' and role not in room['owners'].values():
            player['state'] = 'eliminated'
            announce(room, 'elimination', f'{role.title()} commander eliminated.', role=role)


def after_position(room, board):
    eliminate(room)
    room['fen'] = board.fen()
    if board.is_checkmate():
        finish_game(room, 'victory' if board.turn == chess.BLACK else 'defeat', 'Checkmate. The human team wins.' if board.turn == chess.BLACK else 'Checkmate. The human team is defeated.')
        return
    if board.is_stalemate():
        room.update(phase='stalled', deadline=None, draw_notice='Stalemate. The match remains open. Four votes are needed to restart.')
        announce(room, 'stalemate', room['draw_notice'])
        return
    room['draw_notice'] = 'A standard draw condition is present. War Chess continues.' if board.is_insufficient_material() or board.can_claim_draw() or board.is_seventyfive_moves() or board.is_fivefold_repetition() else None
    if board.turn == chess.WHITE:
        room.update(phase='strategy', deadline=time.time() + 60)
        announce(room, 'strategy', 'Strategy time. Your team has one minute.')
    else:
        room.update(phase='ai', deadline=None)


def execute_move(room, board, move, actor):
    start, dest = chess.square_name(move.from_square), chess.square_name(move.to_square)
    piece = board.piece_at(move.from_square)
    capture = board.is_capture(move)
    captured_square = move.to_square
    if board.is_en_passant(move):
        captured_square += -8 if piece.color else 8
    captured = board.piece_at(captured_square) if capture else None
    owner = room['owners'].pop(start, None)
    room['owners'].pop(chess.square_name(captured_square), None)
    if owner:
        room['owners'][dest] = owner
    if board.is_castling(move) and piece.color == chess.WHITE:
        rook_start, rook_end = ('h1', 'f1') if move.to_square > move.from_square else ('a1', 'd1')
        rook_owner = room['owners'].pop(rook_start, 'rook')
        room['owners'][rook_end] = rook_owner
    san = board.san(move)
    # Visual jump is only used if the first square along the knight's long axis is occupied.
    dx = chess.square_file(move.to_square) - chess.square_file(move.from_square)
    dy = chess.square_rank(move.to_square) - chess.square_rank(move.from_square)
    jump = False
    if piece.piece_type == chess.KNIGHT:
        intermediate = move.from_square + ((8 if dy > 0 else -8) if abs(dy) == 2 else (1 if dx > 0 else -1))
        jump = bool(board.piece_at(intermediate))
    board.push(move)
    room['moves'].append(move.uci())
    room['position_version'] += 1
    room['approvals'] = []
    room['last_move'] = {'from': start, 'to': dest, 'san': san, 'capture': capture, 'piece': piece.symbol(), 'jump': jump, 'actor': actor}
    room['history'].append({'san': san, 'uci': move.uci(), 'actor': actor, 'capture': capture})
    if piece.color == chess.WHITE:
        room['human_moves'] += 1
    announce(room, 'capture' if capture else 'move', f'{actor}: {san}', captured=TYPE_ROLE[captured.piece_type] if captured else None)
    after_position(room, board)
    if move.promotion and piece.color == chess.WHITE and room['status'] == 'active' and room['phase'] != 'stalled':
        target = TYPE_ROLE[move.promotion]
        target_player = room['players'].get(target)
        if target_player and target_player['state'] == 'spectating':
            room['promotion'] = {'square': dest, 'role': target, 'expires': time.time() + 30}
            room.update(phase='promotion', deadline=None)
        announce(room, 'promotion', f'Pawn promoted to {target.title()}. Control stays with Pawn unless transferred.')


def reset_board(room):
    room.update(status='lobby', phase='lobby', fen=chess.STARTING_FEN, moves=[], history=[], owners=initial_owners(), human_moves=0,
                command_count=0, position_version=0, approvals=[], deadline=None, last_move=None, result=None, result_reason=None,
                promotion=None, draw_notice=None, votes={}, restart_requested=False, round_id=str(uuid.uuid4()))
    room['players'] = {r: {**p, 'state': 'active', 'ready': False} for r, p in room['players'].items() if p['state'] != 'left'}


def public_state(room):
    out = {k: v for k, v in room.items() if k not in ('_id', 'voice_room')}
    out['server_time'] = time.time()
    board = board_for(room)
    out['legal_moves'] = [m.uci() for m in board.legal_moves] if room['status'] == 'active' and board.turn == chess.WHITE else []
    out['in_check'] = board.is_check()
    return out