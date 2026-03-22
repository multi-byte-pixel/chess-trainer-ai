"""Position explorer tool handlers using ChessDB.

Provides MCP tools for exploring chess positions via the ChessDB
crowd-sourced analysis database.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Optional

from data.chessdb_client import ChessDBClient
from data.storage import RedisCache
from utils.config import get_settings

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


async def _get_chessdb_cached(
    fen: str,
    action: str,
    client: ChessDBClient,
    cache: RedisCache,
) -> Optional[dict[str, Any]]:
    """Fetch ChessDB data with Redis caching."""
    settings = get_settings()
    cache_key = f"chessdb:{action}:{fen}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    if action == "queryall":
        result = await client.query_all(fen)
    elif action == "querybest":
        result = await client.query_best(fen)
    elif action == "querypv":
        result = await client.query_pv(fen)
    else:
        return None

    await cache.set(cache_key, result, ttl=settings.chessdb_cache_ttl)
    return result


# ------------------------------------------------------------------
# Tool handlers
# ------------------------------------------------------------------


async def explore_position(
    args: dict[str, Any],
    client: ChessDBClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Explore a position using ChessDB – returns all scored candidate moves.

    This is the primary exploration tool: given a FEN it returns every
    move ChessDB has analysed along with scores, ranks and win-rates.
    """
    fen: str = args["fen"]
    data = await _get_chessdb_cached(fen, "queryall", client, cache)
    if data is None:
        return {"fen": fen, "status": "not_found", "moves": []}
    return {**data, "fen": fen}


async def explore_best_move(
    args: dict[str, Any],
    client: ChessDBClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Get the single best move for a position from ChessDB."""
    fen: str = args["fen"]
    data = await _get_chessdb_cached(fen, "querybest", client, cache)
    if data is None:
        return {"fen": fen, "status": "not_found", "move": None}
    return {**data, "fen": fen}


async def explore_principal_variation(
    args: dict[str, Any],
    client: ChessDBClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Get the principal variation from a position from ChessDB."""
    fen: str = args["fen"]
    data = await _get_chessdb_cached(fen, "querypv", client, cache)
    if data is None:
        return {"fen": fen, "status": "not_found", "pv": ""}
    return {**data, "fen": fen}


async def queue_position_analysis(
    args: dict[str, Any],
    client: ChessDBClient,
) -> dict[str, Any]:
    """Queue a position for server-side analysis on ChessDB.

    Use this when a position is not yet in the database and you want
    ChessDB to analyse it.
    """
    fen: str = args["fen"]
    result = await client.queue_position(fen)
    return {"fen": fen, **result}
