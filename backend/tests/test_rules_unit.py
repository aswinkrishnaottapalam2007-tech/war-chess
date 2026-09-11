import chess
import pytest
from fastapi import HTTPException

import rules


# Rule-level unit checks for approvals and anti-cheat validation.


def test_approval_required_matrix():
    # Queen capture always requires king approval.
    board_q = chess.Board('8/8/8/3p4/4Q3/8/8/4K3 w - - 0 1')
    room_q = {'human_moves': 0, 'owners': {'e4': 'queen', 'e1': 'king'}}
    assert rules.approval_required(room_q, board_q, chess.Move.from_uci('e4d5'), 'queen') is True

    # Pawn captures never require approval.
    board_p = chess.Board('8/8/8/3p4/4P3/8/8/4K3 w - - 0 1')
    room_p = {'human_moves': 10, 'owners': {'e4': 'pawn', 'e1': 'king'}}
    assert rules.approval_required(room_p, board_p, chess.Move.from_uci('e4d5'), 'pawn') is False

    # Rook capture free during first four human-team turns.
    board_r = chess.Board('8/8/8/8/8/8/r7/R3K3 w Q - 0 1')
    room_r_open = {'human_moves': 3, 'owners': {'a1': 'rook', 'e1': 'king'}}
    assert rules.approval_required(room_r_open, board_r, chess.Move.from_uci('a1a2'), 'rook') is False

    # Same capture requires approval after opening freedom window.
    room_r_late = {'human_moves': 4, 'owners': {'a1': 'rook', 'e1': 'king'}}
    assert rules.approval_required(room_r_late, board_r, chess.Move.from_uci('a1a2'), 'rook') is True

    # Lone surviving rook may move freely (non-capture) after opening window.
    board_move = chess.Board('8/8/8/8/8/8/8/R3K3 w Q - 0 1')
    room_lone = {'human_moves': 7, 'owners': {'a1': 'rook', 'e1': 'king'}}
    assert rules.approval_required(room_lone, board_move, chess.Move.from_uci('a1a3'), 'rook') is False


def test_validate_move_ownership_and_stale_version_with_monkeypatched_board_for(monkeypatch):
    board = chess.Board()
    monkeypatch.setattr(rules, 'board_for', lambda _room: board)

    room = {
        'status': 'active',
        'phase': 'strategy',
        'position_version': 5,
        'owners': {'e2': 'pawn', 'e1': 'king'},
        'players': {
            'pawn': {'id': 'u_pawn', 'state': 'active', 'role': 'pawn'},
            'queen': {'id': 'u_queen', 'state': 'active', 'role': 'queen'},
            'king': {'id': 'u_king', 'state': 'active', 'role': 'king'},
        },
    }

    with pytest.raises(HTTPException) as stale:
        rules.validate_move(room, 'u_pawn', 'e2e4', 4)
    assert stale.value.status_code == 409

    with pytest.raises(HTTPException) as wrong_owner:
        rules.validate_move(room, 'u_queen', 'e2e4', 5)
    assert wrong_owner.value.status_code == 403
