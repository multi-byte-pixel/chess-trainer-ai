"""Endgame tablebase bridge tool handlers.

Provides MCP tools for probing Syzygy endgame tablebases via the
Lichess Tablebase API, with local caching.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import chess

from chess_engine.position_analyzer import PositionAnalyzer
from chess_engine.stockfish_wrapper import StockfishEngine
from data.storage import RedisCache
from data.tablebase_client import TablebaseClient
from utils.config import get_settings

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


async def _get_tablebase_cached(
    fen: str,
    client: TablebaseClient,
    cache: RedisCache,
) -> Optional[dict[str, Any]]:
    """Probe the tablebase with caching."""
    settings = get_settings()
    cache_key = f"tablebase:{fen}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await client.probe_position(fen)
    if result is None:
        return None

    await cache.set(cache_key, result, ttl=settings.tablebase_cache_ttl)
    return result


# ------------------------------------------------------------------
# Tool handlers
# ------------------------------------------------------------------


async def probe_tablebase(
    args: dict[str, Any],
    tablebase_client: TablebaseClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Probe the Syzygy endgame tablebase for a position.

    Returns the tablebase evaluation (win/draw/loss), DTZ (distance
    to zeroing), and the optimal moves with their evaluations.
    Works for positions with up to 7 pieces.
    """
    fen: str = args["fen"]

    # Validate piece count
    try:
        board = chess.Board(fen)
    except ValueError:
        return {"error": "Invalid FEN", "fen": fen}

    piece_count = len(board.piece_map())
    if piece_count > 7:
        return {
            "fen": fen,
            "error": f"Position has {piece_count} pieces; tablebase supports up to 7.",
            "available": False,
        }

    result = await _get_tablebase_cached(fen, tablebase_client, cache)
    if result is None:
        return {"fen": fen, "available": False, "reason": "Position not in tablebase"}

    return {"fen": fen, "available": True, **result}


async def probe_tablebase_mainline(
    args: dict[str, Any],
    tablebase_client: TablebaseClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Get the optimal play sequence (mainline) from a tablebase position.

    Returns the sequence of moves that leads to the tablebase outcome.
    """
    fen: str = args["fen"]

    result = await tablebase_client.mainline(fen)
    if result is None:
        return {"fen": fen, "available": False}

    return {"fen": fen, "available": True, **result}


async def endgame_analysis(
    args: dict[str, Any],
    engine: StockfishEngine,
    tablebase_client: TablebaseClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Combined endgame analysis using both Stockfish and tablebases.

    For positions with ≤7 pieces, queries the tablebase for perfect
    play information. For all positions, also runs Stockfish for a
    practical evaluation. Compares the two when both are available.
    """
    fen: str = args["fen"]
    depth: int = args.get("depth", 25)

    # Classify the endgame
    analyzer = PositionAnalyzer(engine)
    endgame_type = analyzer.classify_endgame(fen)

    # Engine analysis
    engine_result = await engine.analyze(fen, depth=depth, multipv=1)
    engine_best = engine_result.best_move or ""
    engine_cp = engine_result.best_line.cp if engine_result.best_line else None
    engine_mate = engine_result.best_line.mate if engine_result.best_line else None

    # Tablebase probe (if ≤7 pieces)
    try:
        board = chess.Board(fen)
        piece_count = len(board.piece_map())
    except ValueError:
        piece_count = 99

    tb_result: Optional[dict[str, Any]] = None
    if piece_count <= 7:
        tb_result = await _get_tablebase_cached(fen, tablebase_client, cache)

    # Build response
    response: dict[str, Any] = {
        "fen": fen,
        "endgame_type": endgame_type,
        "piece_count": piece_count,
        "engine": {
            "best_move": engine_best,
            "cp": engine_cp,
            "mate": engine_mate,
            "depth": depth,
        },
    }

    if tb_result:
        response["tablebase"] = {
            "available": True,
            "category": tb_result.get("category"),
            "dtz": tb_result.get("dtz"),
            "dtm": tb_result.get("dtm"),
        }

        # Check if engine and tablebase agree
        tb_moves = tb_result.get("moves", [])
        tb_best = tb_moves[0].get("uci", "") if tb_moves else ""
        response["agreement"] = engine_best == tb_best if engine_best and tb_best else None
        response["tablebase_best_move"] = tb_best
    else:
        response["tablebase"] = {"available": False}

    return response
