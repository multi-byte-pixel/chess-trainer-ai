"""Position analysis helpers: blunder detection, ACPL calculation."""
from __future__ import annotations

import logging
from typing import Optional

import chess
import chess.pgn

from chess_engine.stockfish_wrapper import StockfishEngine
from data.models import AnalysisResult, BlunderInfo

logger = logging.getLogger(__name__)

# Centipawn thresholds for classification
_BLUNDER_THRESHOLD = 200
_MISTAKE_THRESHOLD = 100
_INACCURACY_THRESHOLD = 50


def classify_cp_loss(cp_loss: int) -> str:
    """Return blunder / mistake / inaccuracy / ok for a given cp loss."""
    if cp_loss >= _BLUNDER_THRESHOLD:
        return "blunder"
    if cp_loss >= _MISTAKE_THRESHOLD:
        return "mistake"
    if cp_loss >= _INACCURACY_THRESHOLD:
        return "inaccuracy"
    return "ok"


def score_to_float(line: Optional[object]) -> Optional[float]:
    """Return a normalised float score from an AnalysisLine (cp or mate sentinel)."""
    if line is None:
        return None
    from data.models import AnalysisLine

    assert isinstance(line, AnalysisLine)
    if line.mate is not None:
        return 30000.0 if line.mate > 0 else -30000.0
    return float(line.cp) if line.cp is not None else None


class PositionAnalyzer:
    """Higher-level analysis: blunder detection, ACPL, endgame classification."""

    def __init__(self, engine: StockfishEngine) -> None:
        self._engine = engine

    async def find_blunders(
        self,
        pgn: str,
        depth: int = 18,
    ) -> list[BlunderInfo]:
        """
        Analyse every move in a PGN and return blunders/mistakes/inaccuracies.
        """
        try:
            game = chess.pgn.read_game(__import__("io").StringIO(pgn))
        except Exception as exc:
            logger.error("Failed to parse PGN: %s", exc)
            return []

        if game is None:
            return []

        blunders: list[BlunderInfo] = []
        board = game.board()
        node = game

        prev_score: Optional[float] = None

        for move in game.mainline_moves():
            fen_before = board.fen()
            color = "white" if board.turn == chess.WHITE else "black"

            result_before: AnalysisResult = await self._engine.analyze(fen_before, depth=depth, multipv=1)
            score_before = score_to_float(result_before.best_line)
            best_move = result_before.best_move or move.uci()

            board.push(move)
            fen_after = board.fen()

            result_after: AnalysisResult = await self._engine.analyze(fen_after, depth=depth, multipv=1)
            score_after_raw = score_to_float(result_after.best_line)

            # After the move the score is from the opponent's perspective; negate
            score_after = -score_after_raw if score_after_raw is not None else None

            if score_before is not None and score_after is not None:
                # cp_loss from the moving side's perspective
                cp_loss = int(score_before - score_after)
                classification = classify_cp_loss(max(0, cp_loss))
                if classification != "ok":
                    move_number = board.fullmove_number if color == "black" else board.fullmove_number - 1
                    blunders.append(
                        BlunderInfo(
                            move_number=move_number,
                            ply=board.ply(),
                            color=color,
                            played_move=move.uci(),
                            best_move=best_move,
                            played_cp=int(score_after) if score_after is not None else None,
                            best_cp=int(score_before) if score_before is not None else None,
                            cp_loss=max(0, cp_loss),
                            fen_before=fen_before,
                            fen_after=fen_after,
                            classification=classification,
                        )
                    )
            prev_score = score_after

        return blunders

    async def calculate_acpl(self, pgn: str, depth: int = 18) -> Optional[float]:
        """Calculate the Average Centipawn Loss for a game."""
        blunders = await self.find_blunders(pgn, depth=depth)
        if not blunders:
            return 0.0
        total_loss = sum(b.cp_loss for b in blunders)
        # Divide by total moves (approximated by ply / 2 for the moving side)
        try:
            game = chess.pgn.read_game(__import__("io").StringIO(pgn))
            board = game.board()  # type: ignore[union-attr]
            total_moves = sum(1 for _ in game.mainline_moves())  # type: ignore[union-attr]
        except Exception:
            total_moves = len(blunders) * 2  # fallback
        if total_moves == 0:
            return None
        return round(total_loss / total_moves, 1)

    def classify_endgame(self, fen: str) -> str:
        """Return a human-readable endgame classification for the position."""
        try:
            board = chess.Board(fen)
        except ValueError:
            return "unknown"

        pieces = board.piece_map()
        piece_types = [p.piece_type for p in pieces.values()]

        pawns = piece_types.count(chess.PAWN)
        rooks = piece_types.count(chess.ROOK)
        queens = piece_types.count(chess.QUEEN)
        bishops = piece_types.count(chess.BISHOP)
        knights = piece_types.count(chess.KNIGHT)
        minors = bishops + knights
        total_non_king = len(pieces) - 2  # subtract two kings

        if queens:
            return "queen endgame"
        if rooks and not minors and not pawns:
            return "rook endgame"
        if rooks:
            return "rook and pawn endgame"
        if minors == 1 and not rooks:
            return "minor piece endgame"
        if pawns and not rooks and not minors:
            return "king and pawn endgame"
        if total_non_king == 0:
            return "king vs king"
        return "mixed endgame"
