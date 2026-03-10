"""Game and puzzle fetch tool handlers."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from data.lichess_client import LichessClient
from data.storage import RedisCache
from utils.config import get_settings

logger = logging.getLogger(__name__)


async def fetch_lichess_games(args: dict[str, Any], client: LichessClient, cache: RedisCache) -> dict[str, Any]:
    """Fetch recent games for a Lichess user."""
    username: str = args["username"]
    max_games: int = args.get("max_games", 20)
    since: int | None = args.get("since")
    rated: bool | None = args.get("rated")
    perf_type: str | None = args.get("perf_type")
    color: str | None = args.get("color")

    settings = get_settings()
    cache_key = f"games:{username}:{max_games}:{since}:{rated}:{perf_type}:{color}"
    cached = await cache.get(cache_key)
    if cached:
        return {"source": "cache", "games": cached}

    games = await client.get_games(
        username,
        max_games=max_games,
        since=since,
        rated=rated,
        perf_type=perf_type,
        color=color,
    )
    serialized = [asdict(g) for g in games]
    await cache.set(cache_key, serialized, ttl=settings.games_cache_ttl)
    return {"source": "lichess", "games": serialized}


async def fetch_puzzle_activity(args: dict[str, Any], client: LichessClient, cache: RedisCache) -> dict[str, Any]:
    """Fetch puzzle activity for a Lichess user."""
    username: str = args["username"]
    max_puzzles: int = args.get("max_puzzles", 50)
    before: int | None = args.get("before")

    cache_key = f"puzzles:{username}:{max_puzzles}:{before}"
    cached = await cache.get(cache_key)
    if cached:
        return {"source": "cache", "puzzles": cached}

    puzzles = await client.get_puzzle_activity(username, max_puzzles=max_puzzles, before=before)
    serialized = [asdict(p) for p in puzzles]
    await cache.set(cache_key, serialized, ttl=3600)
    return {"source": "lichess", "puzzles": serialized}
