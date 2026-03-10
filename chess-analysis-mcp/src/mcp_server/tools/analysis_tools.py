"""Analysis tool handlers: blunders, ACPL, cloud eval, compare, annotate."""
from __future__ import annotations

import io
import json
import logging
from dataclasses import asdict
from typing import Any, Optional

import chess
import chess.pgn

from chess_engine.stockfish_wrapper import StockfishEngine
from data.lichess_client import LichessClient
from data.models import AnalysisResult, CloudEvalResult
from data.storage import RedisCache
from utils.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_cloud_eval_cached(
    fen: str,
    multi_pv: int,
    variant: str,
    client: LichessClient,
    cache: RedisCache,
) -> Optional[dict[str, Any]]:
    settings = get_settings()
    cache_key = f"cloud_eval:{fen}:{multi_pv}:{variant}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await client.get_cloud_eval(fen, multi_pv=multi_pv, variant=variant)
    if result is None:
        return None
    serialized = asdict(result)
    await cache.set(cache_key, serialized, ttl=settings.cloud_eval_cache_ttl)
    return serialized


def _analysis_to_dict(result: AnalysisResult) -> dict[str, Any]:
    return {
        "fen": result.fen,
        "depth": result.depth,
        "elapsed_ms": result.elapsed_ms,
        "best_move": result.best_move,
        "lines": [
            {
                "rank": line.multipv_rank,
                "depth": line.depth,
                "cp": line.cp,
                "mate": line.mate,
                "pv": line.pv,
            }
            for line in result.lines
        ],
    }


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


async def fetch_cloud_eval(
    args: dict[str, Any],
    client: LichessClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Return cloud evaluation for a position (cached)."""
    fen: str = args["fen"]
    multi_pv: int = args.get("multi_pv", 3)
    variant: str = args.get("variant", "standard")

    data = await _get_cloud_eval_cached(fen, multi_pv, variant, client, cache)
    if data is None:
        return {"fen": fen, "evaluations": [], "available": False}
    return {"available": True, **data}


async def analyze_position(
    args: dict[str, Any],
    engine: StockfishEngine,
) -> dict[str, Any]:
    """Analyse a position with local Stockfish."""
    fen: str = args["fen"]
    depth: int = args.get("depth", 20)
    multipv: int = args.get("multipv", 1)
    time_limit: Optional[float] = args.get("time_limit")

    result = await engine.analyze(fen, depth=depth, multipv=multipv, time_limit=time_limit)
    return _analysis_to_dict(result)


async def compare_to_engine(
    args: dict[str, Any],
    engine: StockfishEngine,
) -> dict[str, Any]:
    """Compare a played move to the engine's best move."""
    fen: str = args["fen"]
    played_move: str = args["played_move"]
    depth: int = args.get("depth", 20)

    result = await engine.analyze(fen, depth=depth, multipv=3)
    best_move = result.best_move or ""
    best_cp = result.best_line.cp if result.best_line else None
    is_best = played_move == best_move

    return {
        "fen": fen,
        "played_move": played_move,
        "best_move": best_move,
        "is_best_move": is_best,
        "best_cp": best_cp,
        "lines": _analysis_to_dict(result)["lines"],
    }


async def compare_position_vs_cloud(
    args: dict[str, Any],
    engine: StockfishEngine,
    client: LichessClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Compare local Stockfish evaluation with Lichess Cloud Eval."""
    fen: str = args["fen"]
    local_depth: int = args.get("local_depth", 20)
    multi_pv: int = args.get("multi_pv", 3)

    # Run both concurrently
    import asyncio

    local_task = asyncio.create_task(engine.analyze(fen, depth=local_depth, multipv=multi_pv))
    cloud_task = asyncio.create_task(
        _get_cloud_eval_cached(fen, multi_pv, "standard", client, cache)
    )
    local_result, cloud_data = await asyncio.gather(local_task, cloud_task)

    local_dict = _analysis_to_dict(local_result)
    local_best_move = local_result.best_move or ""
    local_cp = local_result.best_line.cp if local_result.best_line else None

    if cloud_data is None or not cloud_data.get("evaluations"):
        return {
            "fen": fen,
            "local_eval": local_dict,
            "cloud_eval": None,
            "agreement": None,
            "novelty_score": None,
        }

    cloud_evals = cloud_data["evaluations"]
    cloud_best_pv: str = cloud_evals[0].get("pv", "") if cloud_evals else ""
    cloud_best_move = cloud_best_pv.split()[0] if cloud_best_pv else ""
    cloud_cp = cloud_evals[0].get("cp") if cloud_evals else None

    # Agreement: is the local best move in any of the cloud top lines?
    cloud_first_moves = {e.get("pv", "").split()[0] for e in cloud_evals if e.get("pv")}
    agreement = local_best_move in cloud_first_moves if local_best_move else None

    # Novelty score: high when best moves differ and cp difference is large
    cp_diff = None
    if local_cp is not None and cloud_cp is not None:
        cp_diff = abs(local_cp - cloud_cp)
    novelty_score = _compute_novelty(local_best_move, cloud_best_move, cp_diff)

    return {
        "fen": fen,
        "local_eval": local_dict,
        "cloud_eval": cloud_data,
        "agreement": agreement,
        "cp_difference": cp_diff,
        "novelty_score": novelty_score,
    }


def _compute_novelty(local_move: str, cloud_move: str, cp_diff: Optional[int]) -> str:
    if local_move and cloud_move and local_move != cloud_move:
        if cp_diff is not None and cp_diff > 100:
            return "high"
        return "medium"
    return "low"


async def annotate_game_with_cloud_eval(
    args: dict[str, Any],
    engine: StockfishEngine,
    client: LichessClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Annotate positions in a game with both local and cloud evaluations."""
    pgn: str = args["pgn"]
    sample_strategy: str = args.get("sample_strategy", "every_move")
    max_cloud_queries: int = args.get("max_cloud_queries", 10)
    local_depth: int = args.get("local_depth", 18)
    multi_pv: int = args.get("multi_pv", 1)

    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception as exc:
        return {"error": f"Failed to parse PGN: {exc}", "positions": []}

    if game is None:
        return {"error": "Empty PGN", "positions": []}

    board = game.board()
    positions: list[dict[str, Any]] = []
    cloud_queries_used = 0

    prev_cp: Optional[int] = None
    fen_list: list[tuple[int, str, str]] = []  # (move_number, fen, move_uci)

    for move in game.mainline_moves():
        fen = board.fen()
        move_num = board.fullmove_number
        fen_list.append((move_num, fen, move.uci()))
        board.push(move)

    # Decide which positions to sample
    if sample_strategy == "every_move":
        sampled = fen_list[:max_cloud_queries]
    elif sample_strategy == "critical_only":
        sampled = await _select_critical(fen_list, engine, local_depth, max_cloud_queries)
    else:
        sampled = fen_list[:max_cloud_queries]

    import asyncio

    for move_number, fen, move_uci in sampled:
        if cloud_queries_used >= max_cloud_queries:
            break

        local_task = asyncio.create_task(engine.analyze(fen, depth=local_depth, multipv=multi_pv))
        cloud_task = asyncio.create_task(
            _get_cloud_eval_cached(fen, multi_pv, "standard", client, cache)
        )
        local_result, cloud_data = await asyncio.gather(local_task, cloud_task)
        cloud_queries_used += 1

        local_dict = _analysis_to_dict(local_result)
        comment = _build_comment(local_result, cloud_data)
        positions.append(
            {
                "move_number": move_number,
                "move": move_uci,
                "fen": fen,
                "local_eval": local_dict,
                "cloud_eval": cloud_data,
                "comment": comment,
            }
        )

    return {"positions": positions, "cloud_queries_used": cloud_queries_used}


async def _select_critical(
    fen_list: list[tuple[int, str, str]],
    engine: StockfishEngine,
    depth: int,
    max_n: int,
) -> list[tuple[int, str, str]]:
    """Select positions around large evaluation swings (critical moments)."""
    if len(fen_list) <= max_n:
        return fen_list

    scores: list[tuple[int, str, str, Optional[int]]] = []
    for move_number, fen, uci in fen_list:
        result = await engine.analyze(fen, depth=depth, multipv=1)
        cp = result.best_line.cp if result.best_line else None
        scores.append((move_number, fen, uci, cp))

    swings: list[tuple[float, int, str, str]] = []
    for i in range(1, len(scores)):
        prev_cp = scores[i - 1][3]
        curr_cp = scores[i][3]
        if prev_cp is not None and curr_cp is not None:
            swing = abs(curr_cp - prev_cp)
        else:
            swing = 0.0
        swings.append((swing, scores[i][0], scores[i][1], scores[i][2]))

    swings.sort(key=lambda x: x[0], reverse=True)
    return [(mn, fen, uci) for _, mn, fen, uci in swings[:max_n]]


def _build_comment(local_result: AnalysisResult, cloud_data: Optional[dict[str, Any]]) -> str:
    parts: list[str] = []
    if local_result.best_line:
        cp = local_result.best_line.cp
        mate = local_result.best_line.mate
        if mate is not None:
            parts.append(f"Local: M{mate}")
        elif cp is not None:
            parts.append(f"Local: {cp:+d}cp")

    if cloud_data and cloud_data.get("evaluations"):
        ev = cloud_data["evaluations"][0]
        cp = ev.get("cp")
        mate = ev.get("mate")
        if mate is not None:
            parts.append(f"Cloud: M{mate}")
        elif cp is not None:
            parts.append(f"Cloud: {cp:+d}cp")

    return " | ".join(parts) if parts else ""
