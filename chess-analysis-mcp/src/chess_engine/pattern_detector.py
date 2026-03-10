"""Tactical pattern detection in chess positions."""
from __future__ import annotations

import chess
import chess.pgn

PATTERN_NAMES = [
    "fork",
    "pin",
    "skewer",
    "discovered_attack",
    "double_check",
    "back_rank_weakness",
    "hanging_piece",
]


def detect_fork(board: chess.Board) -> bool:
    """Return True if the side to move has a forking move available."""
    for move in board.legal_moves:
        board.push(move)
        attacks = 0
        mover = not board.turn  # the piece that just moved
        piece = board.piece_at(move.to_square)
        if piece is None:
            board.pop()
            continue
        attacked_squares = board.attacks(move.to_square)
        for sq in attacked_squares:
            victim = board.piece_at(sq)
            if victim and victim.color == board.turn:
                attacks += 1
        board.pop()
        if attacks >= 2:
            return True
    return False


def detect_hanging_pieces(board: chess.Board) -> list[chess.Square]:
    """Return list of squares with hanging (undefended, attacked) pieces."""
    hanging: list[chess.Square] = []
    side_to_move = board.turn
    for sq, piece in board.piece_map().items():
        if piece.color == (not side_to_move):
            if board.is_attacked_by(side_to_move, sq) and not board.is_attacked_by(not side_to_move, sq):
                hanging.append(sq)
    return hanging


def detect_back_rank_weakness(board: chess.Board) -> bool:
    """Detect whether the opponent king has a back-rank weakness."""
    side_to_move = board.turn
    opponent = not side_to_move
    king_sq = board.king(opponent)
    if king_sq is None:
        return False
    back_rank = chess.BB_RANK_1 if opponent == chess.WHITE else chess.BB_RANK_8
    if not (chess.BB_SQUARES[king_sq] & back_rank):
        return False
    # Check for rooks/queens on the back rank that can deliver checkmate
    for sq in chess.scan_forward(back_rank & board.occupied_co[side_to_move]):
        piece = board.piece_at(sq)
        if piece and piece.piece_type in (chess.ROOK, chess.QUEEN):
            return True
    return False


def detect_patterns(fen: str) -> dict[str, bool]:
    """
    Detect common tactical patterns in a position.
    Returns a dict mapping pattern name -> bool.
    """
    try:
        board = chess.Board(fen)
    except ValueError:
        return {name: False for name in PATTERN_NAMES}

    patterns: dict[str, bool] = {
        "fork": detect_fork(board),
        "pin": _detect_pin(board),
        "skewer": _detect_skewer(board),
        "discovered_attack": _detect_discovered_attack(board),
        "double_check": _detect_double_check(board),
        "back_rank_weakness": detect_back_rank_weakness(board),
        "hanging_piece": len(detect_hanging_pieces(board)) > 0,
    }
    return patterns


# ------------------------------------------------------------------
# Simplified pattern detectors
# ------------------------------------------------------------------


def _detect_pin(board: chess.Board) -> bool:
    """Simplified pin detection: look for absolute pins."""
    for sq, piece in board.piece_map().items():
        if piece.color == board.turn:
            if board.is_pinned(piece.color, sq):
                return True
    return False


def _detect_skewer(board: chess.Board) -> bool:
    """Very simplified skewer: a high-value piece is attacked along a ray."""
    high_value = {chess.QUEEN, chess.ROOK, chess.KING}
    side = board.turn
    for sq, piece in board.piece_map().items():
        if piece.color != side and piece.piece_type in high_value:
            if board.is_attacked_by(side, sq):
                return True
    return False


def _detect_discovered_attack(board: chess.Board) -> bool:
    """Check if any move reveals an attack by a sliding piece behind it."""
    for move in board.legal_moves:
        if board.is_capture(move):
            continue
        board.push(move)
        # Check if the opponent king is in check – which implies discovered check
        in_check = board.is_check()
        board.pop()
        if in_check:
            # Verify it's not a direct check by the moved piece
            moving_piece = board.piece_at(move.from_square)
            if moving_piece:
                test_board = board.copy()
                test_board.push(move)
                direct_attackers = test_board.attackers(board.turn, test_board.king(not board.turn))
                if move.to_square not in direct_attackers:
                    return True
    return False


def _detect_double_check(board: chess.Board) -> bool:
    """Return True if any legal move gives double check."""
    for move in board.legal_moves:
        board.push(move)
        if board.is_check():
            attackers = list(board.attackers(not board.turn, board.king(board.turn)))
            board.pop()
            if len(attackers) >= 2:
                return True
        else:
            board.pop()
    return False
