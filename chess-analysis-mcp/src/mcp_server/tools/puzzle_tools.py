"""Puzzle generation tool handlers.

Generates training puzzles from analysed games by identifying
critical positions where the player made a significant mistake
and the engine has a clear winning continuation.
"""
from __future__ import annotations

import io
import logging
from typing import Any, Optional

import chess
import chess.pgn

from chess_engine.position_analyzer import classify_cp_loss
from chess_engine.stockfish_wrapper import StockfishEngine
from data.lichess_client import LichessClient
from data.models import AnalysisResult
from data.storage import RedisCache

logger = logging.getLogger(__name__)


async def generate_puzzles_from_game(
    args: dict[str, Any],
    engine: StockfishEngine,
) -> dict[str, Any]:
    """Generate training puzzles from a PGN game.

    Scans the game for positions where a significant mistake was made.
    For each mistake, the position *before* the mistake becomes a
    puzzle, with the engine's best continuation as the solution.

    Returns a list of :class:`GeneratedPuzzle`-like dicts.
    """
    pgn: str = args["pgn"]
    depth: int = args.get("depth", 20)
    min_cp_loss: int = args.get("min_cp_loss", 150)
    max_puzzles: int = args.get("max_puzzles", 10)
    game_id: Optional[str] = args.get("game_id")

    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception as exc:
        return {"error": f"Failed to parse PGN: {exc}", "puzzles": []}

    if game is None:
        return {"error": "Empty PGN", "puzzles": []}

    board = game.board()
    puzzles: list[dict[str, Any]] = []
    prev_result: Optional[AnalysisResult] = None

    for move in game.mainline_moves():
        fen_before = board.fen()
        color = "white" if board.turn == chess.WHITE else "black"

        result_before = await engine.analyze(fen_before, depth=depth, multipv=3)
        best_move = result_before.best_move or ""
        best_cp = result_before.best_line.cp if result_before.best_line else None

        board.push(move)
        fen_after = board.fen()

        result_after = await engine.analyze(fen_after, depth=depth, multipv=1)
        after_cp = result_after.best_line.cp if result_after.best_line else None

        # Negate because it's from the opponent's perspective after the move
        if after_cp is not None:
            after_cp_adjusted = -after_cp
        else:
            after_cp_adjusted = None

        if best_cp is not None and after_cp_adjusted is not None:
            cp_loss = best_cp - after_cp_adjusted
            if cp_loss >= min_cp_loss and move.uci() != best_move:
                # Build the puzzle solution: engine's best continuation
                solution_moves = []
                if result_before.best_line and result_before.best_line.pv:
                    solution_moves = result_before.best_line.pv.split()[:5]

                themes = _classify_puzzle_themes(
                    fen_before, result_before, cp_loss
                )
                difficulty = _estimate_difficulty(cp_loss, depth)

                puzzles.append({
                    "fen": fen_before,
                    "color_to_move": color,
                    "played_move": move.uci(),
                    "best_move": best_move,
                    "solution_uci": solution_moves,
                    "cp_loss": cp_loss,
                    "themes": themes,
                    "difficulty": difficulty,
                    "source_game_id": game_id,
                })

                if len(puzzles) >= max_puzzles:
                    break

    return {"puzzles": puzzles, "total_positions_analysed": board.ply()}


async def generate_puzzles_from_user_games(
    args: dict[str, Any],
    engine: StockfishEngine,
    client: LichessClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Generate puzzles from a user's recent games.

    Fetches recent games, analyses each, and extracts puzzle
    positions where mistakes were made.
    """
    username: str = args["username"]
    max_games: int = args.get("max_games", 5)
    depth: int = args.get("depth", 18)
    min_cp_loss: int = args.get("min_cp_loss", 150)
    max_puzzles_per_game: int = args.get("max_puzzles_per_game", 3)

    games = await client.get_games(username, max_games=max_games)
    all_puzzles: list[dict[str, Any]] = []

    for g in games:
        if not g.pgn:
            continue
        result = await generate_puzzles_from_game(
            {
                "pgn": g.pgn,
                "depth": depth,
                "min_cp_loss": min_cp_loss,
                "max_puzzles": max_puzzles_per_game,
                "game_id": g.id,
            },
            engine,
        )
        all_puzzles.extend(result.get("puzzles", []))

    return {
        "username": username,
        "games_analysed": len(games),
        "puzzles": all_puzzles,
        "total_puzzles": len(all_puzzles),
    }


def _classify_puzzle_themes(
    fen: str,
    analysis: AnalysisResult,
    cp_loss: int,
) -> list[str]:
    """Heuristically classify puzzle themes based on position and analysis."""
    themes: list[str] = []

    if cp_loss >= 300:
        themes.append("blunder_punishment")
    elif cp_loss >= 150:
        themes.append("tactical_opportunity")

    # Check if the best move is a capture
    try:
        board = chess.Board(fen)
        if analysis.best_move:
            best = chess.Move.from_uci(analysis.best_move)
            if board.is_capture(best):
                themes.append("capture")
            if board.gives_check(best):
                themes.append("check")
    except (ValueError, chess.InvalidMoveError):
        pass

    if analysis.best_line and analysis.best_line.mate is not None:
        themes.append("mating_attack")

    if not themes:
        themes.append("positional")

    return themes


def _estimate_difficulty(cp_loss: int, depth: int) -> str:
    """Estimate puzzle difficulty based on cp loss and depth."""
    if cp_loss >= 500:
        return "easy"  # obvious blunder
    if cp_loss >= 200:
        return "medium"
    return "hard"  # subtle mistake
