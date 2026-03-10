"""Training plan and puzzle suggestion tool handlers."""
from __future__ import annotations

from collections import Counter
from typing import Any

from chess_engine.stockfish_wrapper import StockfishEngine
from data.lichess_client import LichessClient
from data.storage import RedisCache


async def generate_training_plan(
    args: dict[str, Any],
    client: LichessClient,
    engine: StockfishEngine,
    cache: RedisCache,
) -> dict[str, Any]:
    """Generate a personalised training plan based on recent performance."""
    username: str = args["username"]
    max_games: int = args.get("max_games", 30)

    games = await client.get_games(username, max_games=max_games)
    puzzles = await client.get_puzzle_activity(username, max_puzzles=50)

    results: Counter[str] = Counter(g.result for g in games)
    total = len(games) or 1
    win_rate = results["win"] / total

    solved_puzzles = sum(1 for p in puzzles if p.solved)
    puzzle_success = solved_puzzles / len(puzzles) if puzzles else 0.0

    plan: list[str] = []

    if win_rate < 0.4:
        plan.append("Focus on basic tactics – solve 10 puzzles per day.")
    if puzzle_success < 0.6:
        plan.append("Work on pattern recognition: forks, pins, skewers.")

    # Opening weakness detection (simplified)
    opening_results: dict[str, Counter] = {}
    for g in games:
        eco = g.opening_eco or "Unknown"
        if eco not in opening_results:
            opening_results[eco] = Counter()
        opening_results[eco][g.result] += 1

    weak_openings = []
    for eco, cnt in opening_results.items():
        games_in_eco = sum(cnt.values())
        if games_in_eco >= 3 and cnt.get("win", 0) / games_in_eco < 0.35:
            weak_openings.append(eco)

    if weak_openings:
        plan.append(f"Study these openings where you're struggling: {', '.join(weak_openings[:3])}")

    if not plan:
        plan.append("Keep up the good work! Review your recent games for improvements.")

    return {
        "username": username,
        "win_rate": round(win_rate * 100, 1),
        "puzzle_success_rate": round(puzzle_success * 100, 1),
        "plan": plan,
    }


async def suggest_puzzle_set(
    args: dict[str, Any],
    client: LichessClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Suggest a puzzle theme set based on recent puzzle performance."""
    username: str = args["username"]
    max_puzzles: int = args.get("max_puzzles", 100)

    puzzles = await client.get_puzzle_activity(username, max_puzzles=max_puzzles)

    theme_results: dict[str, Counter] = {}
    for p in puzzles:
        for theme in p.themes:
            if theme not in theme_results:
                theme_results[theme] = Counter()
            theme_results[theme]["solved" if p.solved else "failed"] += 1

    # Themes with worst performance
    weak_themes = []
    for theme, cnt in theme_results.items():
        total = cnt["solved"] + cnt["failed"]
        if total >= 2:
            success = cnt["solved"] / total
            weak_themes.append((theme, success, total))

    weak_themes.sort(key=lambda x: x[1])

    suggestions = [
        {"theme": t, "success_rate": round(s * 100, 1), "attempts": n}
        for t, s, n in weak_themes[:5]
    ]

    return {
        "username": username,
        "suggested_themes": suggestions,
        "reason": "Themes where your success rate is lowest.",
    }
