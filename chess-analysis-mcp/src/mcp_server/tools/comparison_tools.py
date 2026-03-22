"""Three-source comparison tool handlers.

Compares evaluations from three sources:
1. Local Stockfish engine
2. Lichess Cloud Eval
3. ChessDB crowd-sourced analysis

This enables deeper insight into positions by cross-referencing
independent analysis sources.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from chess_engine.stockfish_wrapper import StockfishEngine
from data.chessdb_client import ChessDBClient
from data.lichess_client import LichessClient
from data.storage import RedisCache
from mcp_server.tools.analysis_tools import _analysis_to_dict, _get_cloud_eval_cached
from mcp_server.tools.explorer_tools import _get_chessdb_cached
from utils.config import get_settings

logger = logging.getLogger(__name__)


async def compare_three_sources(
    args: dict[str, Any],
    engine: StockfishEngine,
    lichess_client: LichessClient,
    chessdb_client: ChessDBClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Compare evaluations from Stockfish, Lichess Cloud, and ChessDB.

    Returns a unified comparison with agreement/disagreement analysis
    and a consensus recommendation.
    """
    fen: str = args["fen"]
    local_depth: int = args.get("local_depth", 20)
    multi_pv: int = args.get("multi_pv", 3)

    # Run all three queries concurrently
    local_task = asyncio.create_task(
        engine.analyze(fen, depth=local_depth, multipv=multi_pv)
    )
    cloud_task = asyncio.create_task(
        _get_cloud_eval_cached(fen, multi_pv, "standard", lichess_client, cache)
    )
    chessdb_task = asyncio.create_task(
        _get_chessdb_cached(fen, "queryall", chessdb_client, cache)
    )

    local_result, cloud_data, chessdb_data = await asyncio.gather(
        local_task, cloud_task, chessdb_task
    )

    # Parse local result
    local_dict = _analysis_to_dict(local_result)
    local_best = local_result.best_move or ""
    local_cp = local_result.best_line.cp if local_result.best_line else None

    # Parse cloud result
    cloud_best = ""
    cloud_cp: Optional[int] = None
    if cloud_data and cloud_data.get("evaluations"):
        cloud_pv = cloud_data["evaluations"][0].get("pv", "")
        cloud_best = cloud_pv.split()[0] if cloud_pv else ""
        cloud_cp = cloud_data["evaluations"][0].get("cp")

    # Parse ChessDB result
    chessdb_best = ""
    chessdb_score: Optional[int] = None
    if chessdb_data and chessdb_data.get("moves"):
        top_move = chessdb_data["moves"][0]
        chessdb_best = top_move.get("uci", "")
        chessdb_score = top_move.get("score")

    # Agreement analysis
    sources_best = {
        "stockfish": local_best,
        "lichess_cloud": cloud_best,
        "chessdb": chessdb_best,
    }
    active_sources = {k: v for k, v in sources_best.items() if v}
    unique_moves = set(active_sources.values())

    if len(unique_moves) == 1 and len(active_sources) > 1:
        consensus = "full_agreement"
    elif len(unique_moves) == len(active_sources) and len(active_sources) > 1:
        consensus = "full_disagreement"
    elif len(active_sources) > 1:
        consensus = "partial_agreement"
    else:
        consensus = "insufficient_data"

    return {
        "fen": fen,
        "stockfish": {
            "best_move": local_best,
            "cp": local_cp,
            "eval": local_dict,
        },
        "lichess_cloud": {
            "best_move": cloud_best,
            "cp": cloud_cp,
            "available": cloud_data is not None,
            "eval": cloud_data,
        },
        "chessdb": {
            "best_move": chessdb_best,
            "score": chessdb_score,
            "available": chessdb_data is not None and bool(chessdb_data.get("moves")),
            "eval": chessdb_data,
        },
        "consensus": consensus,
        "sources_agree_on_move": len(unique_moves) == 1 if unique_moves else None,
        "unique_best_moves": list(unique_moves),
    }


async def compare_move_rankings(
    args: dict[str, Any],
    engine: StockfishEngine,
    lichess_client: LichessClient,
    chessdb_client: ChessDBClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Compare how each source ranks the top N moves for a position.

    Returns a unified table showing each move and its ranking/score
    from each source.
    """
    fen: str = args["fen"]
    top_n: int = args.get("top_n", 5)
    local_depth: int = args.get("local_depth", 20)

    # Run all three queries concurrently
    local_task = asyncio.create_task(
        engine.analyze(fen, depth=local_depth, multipv=top_n)
    )
    cloud_task = asyncio.create_task(
        _get_cloud_eval_cached(fen, top_n, "standard", lichess_client, cache)
    )
    chessdb_task = asyncio.create_task(
        _get_chessdb_cached(fen, "queryall", chessdb_client, cache)
    )

    local_result, cloud_data, chessdb_data = await asyncio.gather(
        local_task, cloud_task, chessdb_task
    )

    # Collect all unique moves from all sources
    all_moves: dict[str, dict[str, Any]] = {}

    # Stockfish moves
    for line in local_result.lines:
        first_move = line.pv.split()[0] if line.pv else ""
        if first_move:
            if first_move not in all_moves:
                all_moves[first_move] = {"move": first_move}
            all_moves[first_move]["stockfish_rank"] = line.multipv_rank
            all_moves[first_move]["stockfish_cp"] = line.cp
            all_moves[first_move]["stockfish_mate"] = line.mate

    # Cloud moves
    if cloud_data and cloud_data.get("evaluations"):
        for rank, ev in enumerate(cloud_data["evaluations"], 1):
            pv = ev.get("pv", "")
            first_move = pv.split()[0] if pv else ""
            if first_move:
                if first_move not in all_moves:
                    all_moves[first_move] = {"move": first_move}
                all_moves[first_move]["cloud_rank"] = rank
                all_moves[first_move]["cloud_cp"] = ev.get("cp")
                all_moves[first_move]["cloud_mate"] = ev.get("mate")

    # ChessDB moves
    if chessdb_data and chessdb_data.get("moves"):
        for rank, m in enumerate(chessdb_data["moves"][:top_n], 1):
            uci = m.get("uci", "")
            if uci:
                if uci not in all_moves:
                    all_moves[uci] = {"move": uci}
                all_moves[uci]["chessdb_rank"] = rank
                all_moves[uci]["chessdb_score"] = m.get("score")

    return {
        "fen": fen,
        "top_n": top_n,
        "move_rankings": list(all_moves.values()),
    }
