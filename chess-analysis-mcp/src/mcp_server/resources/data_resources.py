"""MCP resource handlers exposing game and puzzle data."""
from __future__ import annotations

import json
from typing import Any

from data.lichess_client import LichessClient
from data.storage import RedisCache
from utils.config import get_settings


async def get_games_resource(
    username: str,
    client: LichessClient,
    cache: RedisCache,
) -> str:
    """Return serialized games for a user (game://games/{username})."""
    settings = get_settings()
    cache_key = f"resource:games:{username}"
    cached = await cache.get(cache_key)
    if cached:
        return json.dumps(cached)

    games = await client.get_games(username, max_games=20)
    data = [
        {
            "id": g.id,
            "pgn": g.pgn,
            "perf_type": g.perf_type,
            "color": g.color,
            "result": g.result,
            "opening_eco": g.opening_eco,
            "opening_name": g.opening_name,
            "played_at": g.played_at.isoformat() if g.played_at else None,
        }
        for g in games
    ]
    await cache.set(cache_key, data, ttl=settings.games_cache_ttl)
    return json.dumps(data)


async def get_puzzle_resource(
    username: str,
    client: LichessClient,
    cache: RedisCache,
) -> str:
    """Return serialized puzzle activity for a user (puzzle://activity/{username})."""
    cache_key = f"resource:puzzles:{username}"
    cached = await cache.get(cache_key)
    if cached:
        return json.dumps(cached)

    puzzles = await client.get_puzzle_activity(username, max_puzzles=50)
    data = [
        {
            "puzzle_id": p.puzzle_id,
            "rating": p.rating,
            "solved": p.solved,
            "themes": p.themes,
            "played_at": p.played_at.isoformat() if p.played_at else None,
        }
        for p in puzzles
    ]
    await cache.set(cache_key, data, ttl=1800)
    return json.dumps(data)


async def get_analysis_report_resource(
    username: str,
    period: str,
    client: LichessClient,
    cache: RedisCache,
) -> str:
    """Return a serialized analysis report (analysis://report/{username}/{period})."""
    cache_key = f"resource:report:{username}:{period}"
    cached = await cache.get(cache_key)
    if cached:
        return json.dumps(cached)

    games = await client.get_games(username, max_games=30)
    puzzles = await client.get_puzzle_activity(username, max_puzzles=50)

    wins = sum(1 for g in games if g.result == "win")
    losses = sum(1 for g in games if g.result == "loss")
    draws = sum(1 for g in games if g.result == "draw")
    solved = sum(1 for p in puzzles if p.solved)

    report = {
        "username": username,
        "period": period,
        "games": {"total": len(games), "wins": wins, "losses": losses, "draws": draws},
        "puzzles": {"total": len(puzzles), "solved": solved},
    }
    await cache.set(cache_key, report, ttl=3600)
    return json.dumps(report)
