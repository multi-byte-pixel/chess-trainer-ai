"""Game annotation tool handlers using ChessDB.

Extends the existing game annotation (which uses Lichess Cloud Eval)
to include ChessDB evaluations, providing a third data point for
each annotated position.
"""
from __future__ import annotations

import io
import logging
from typing import Any, Optional

import chess
import chess.pgn

from chess_engine.stockfish_wrapper import StockfishEngine
from data.chessdb_client import ChessDBClient
from data.lichess_client import LichessClient
from data.storage import RedisCache
from mcp_server.tools.analysis_tools import _analysis_to_dict, _get_cloud_eval_cached
from mcp_server.tools.explorer_tools import _get_chessdb_cached
from utils.config import get_settings

logger = logging.getLogger(__name__)


async def annotate_game_three_sources(
    args: dict[str, Any],
    engine: StockfishEngine,
    lichess_client: LichessClient,
    chessdb_client: ChessDBClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Annotate a game with evaluations from Stockfish, Lichess Cloud, and ChessDB.

    Returns a list of positions, each annotated with:
    * Local Stockfish eval
    * Lichess Cloud Eval (if available)
    * ChessDB eval (if available)
    * A combined commentary string
    """
    import asyncio

    pgn: str = args["pgn"]
    max_positions: int = args.get("max_positions", 20)
    local_depth: int = args.get("local_depth", 18)
    multi_pv: int = args.get("multi_pv", 1)
    sample_strategy: str = args.get("sample_strategy", "every_move")

    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception as exc:
        return {"error": f"Failed to parse PGN: {exc}", "positions": []}

    if game is None:
        return {"error": "Empty PGN", "positions": []}

    board = game.board()
    fen_list: list[tuple[int, str, str]] = []

    for move in game.mainline_moves():
        fen = board.fen()
        move_num = board.fullmove_number
        fen_list.append((move_num, fen, move.uci()))
        board.push(move)

    # Select positions to annotate
    sampled = fen_list[:max_positions]

    positions: list[dict[str, Any]] = []

    for move_number, fen, move_uci in sampled:
        # Run all three evaluations concurrently
        local_task = asyncio.create_task(
            engine.analyze(fen, depth=local_depth, multipv=multi_pv)
        )
        cloud_task = asyncio.create_task(
            _get_cloud_eval_cached(fen, multi_pv, "standard", lichess_client, cache)
        )
        chessdb_task = asyncio.create_task(
            _get_chessdb_cached(fen, "querybest", chessdb_client, cache)
        )

        local_result, cloud_data, chessdb_data = await asyncio.gather(
            local_task, cloud_task, chessdb_task
        )

        local_dict = _analysis_to_dict(local_result)
        comment = _build_three_source_comment(local_result, cloud_data, chessdb_data)

        positions.append({
            "move_number": move_number,
            "move": move_uci,
            "fen": fen,
            "local_eval": local_dict,
            "cloud_eval": cloud_data,
            "chessdb_eval": chessdb_data,
            "comment": comment,
        })

    return {
        "positions": positions,
        "total_positions": len(fen_list),
        "annotated_positions": len(positions),
    }


def _build_three_source_comment(
    local_result: Any,
    cloud_data: Optional[dict[str, Any]],
    chessdb_data: Optional[dict[str, Any]],
) -> str:
    """Build a human-readable annotation from three eval sources."""
    parts: list[str] = []

    # Local Stockfish
    if local_result.best_line:
        cp = local_result.best_line.cp
        mate = local_result.best_line.mate
        if mate is not None:
            parts.append(f"Stockfish: M{mate}")
        elif cp is not None:
            parts.append(f"Stockfish: {cp:+d}cp")

    # Lichess Cloud
    if cloud_data and cloud_data.get("evaluations"):
        ev = cloud_data["evaluations"][0]
        cp = ev.get("cp")
        mate = ev.get("mate")
        if mate is not None:
            parts.append(f"Cloud: M{mate}")
        elif cp is not None:
            parts.append(f"Cloud: {cp:+d}cp")

    # ChessDB
    if chessdb_data and chessdb_data.get("score") is not None:
        parts.append(f"ChessDB: {chessdb_data['score']:+d}")

    return " | ".join(parts) if parts else ""
