"""Statistics aggregation tool handlers."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from typing import Any

from data.lichess_client import LichessClient
from data.storage import RedisCache


async def aggregate_puzzle_statistics(
    args: dict[str, Any],
    client: LichessClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Aggregate puzzle statistics for a user."""
    username: str = args["username"]
    max_puzzles: int = args.get("max_puzzles", 200)

    cache_key = f"puzzle_stats:{username}:{max_puzzles}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    puzzles = await client.get_puzzle_activity(username, max_puzzles=max_puzzles)

    total = len(puzzles)
    solved = sum(1 for p in puzzles if p.solved)
    failed = total - solved
    theme_counts: Counter[str] = Counter()
    for p in puzzles:
        theme_counts.update(p.themes)

    ratings = [p.rating for p in puzzles if p.rating]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

    result = {
        "username": username,
        "total": total,
        "solved": solved,
        "failed": failed,
        "success_rate": round(solved / total * 100, 1) if total else 0.0,
        "avg_puzzle_rating": avg_rating,
        "top_themes": theme_counts.most_common(10),
    }
    await cache.set(cache_key, result, ttl=1800)
    return result


async def generate_performance_report(
    args: dict[str, Any],
    client: LichessClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Generate a high-level performance report."""
    username: str = args["username"]
    max_games: int = args.get("max_games", 50)

    games = await client.get_games(username, max_games=max_games)

    results: Counter[str] = Counter(g.result for g in games)
    perf_types: Counter[str] = Counter(g.perf_type for g in games)
    ratings = [g.player_rating for g in games if g.player_rating]
    avg_rating = round(sum(ratings) / len(ratings), 0) if ratings else None

    openings: Counter[str] = Counter()
    for g in games:
        if g.opening_eco:
            openings[g.opening_eco] += 1

    return {
        "username": username,
        "total_games": len(games),
        "results": dict(results),
        "perf_types": dict(perf_types),
        "avg_rating": avg_rating,
        "top_openings": openings.most_common(5),
    }


async def analyze_opening_repertoire(
    args: dict[str, Any],
    client: LichessClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Analyse the opening repertoire for a user."""
    username: str = args["username"]
    max_games: int = args.get("max_games", 100)
    color: str | None = args.get("color")

    games = await client.get_games(username, max_games=max_games, color=color)

    eco_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"games": 0, "wins": 0, "losses": 0, "draws": 0})
    for g in games:
        eco = g.opening_eco or "Unknown"
        eco_stats[eco]["games"] += 1
        if g.result == "win":
            eco_stats[eco]["wins"] += 1
        elif g.result == "loss":
            eco_stats[eco]["losses"] += 1
        else:
            eco_stats[eco]["draws"] += 1

    for eco, stats in eco_stats.items():
        if stats["games"] > 0:
            stats["win_rate"] = round(stats["wins"] / stats["games"] * 100, 1)

    return {
        "username": username,
        "color": color,
        "openings": dict(eco_stats),
    }
