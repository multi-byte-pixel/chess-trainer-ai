"""MCP prompt templates for chess analysis."""
from __future__ import annotations

from mcp.types import GetPromptResult, PromptMessage, TextContent


def analyze_recent_games_prompt(username: str, num_games: int = 10) -> GetPromptResult:
    """Prompt template: analyse recent games."""
    text = (
        f"Please analyse the last {num_games} games for Lichess user '{username}'.\n"
        "Use the fetch_lichess_games tool to retrieve the games, then for each game:\n"
        "1. Identify any blunders or mistakes using find_blunders.\n"
        "2. Calculate the average centipawn loss using calculate_acpl.\n"
        "3. Detect tactical patterns with detect_tactical_patterns.\n"
        "Summarise the findings: what themes recur, what openings are weak, and suggest improvements."
    )
    return GetPromptResult(
        description=f"Analyse recent games for {username}",
        messages=[PromptMessage(role="user", content=TextContent(type="text", text=text))],
    )


def puzzle_performance_review_prompt(username: str, max_puzzles: int = 50) -> GetPromptResult:
    """Prompt template: review puzzle performance."""
    text = (
        f"Please review the recent puzzle activity for Lichess user '{username}'.\n"
        f"Fetch up to {max_puzzles} puzzles with fetch_puzzle_activity, then:\n"
        "1. Aggregate statistics with aggregate_puzzle_statistics.\n"
        "2. Identify themes where the user struggles most.\n"
        "3. Suggest a focused puzzle set with suggest_puzzle_set.\n"
        "Provide actionable recommendations to improve tactical vision."
    )
    return GetPromptResult(
        description=f"Puzzle performance review for {username}",
        messages=[PromptMessage(role="user", content=TextContent(type="text", text=text))],
    )


def opening_repertoire_audit_prompt(username: str, color: str = "white") -> GetPromptResult:
    """Prompt template: opening repertoire audit."""
    text = (
        f"Please audit the opening repertoire for Lichess user '{username}' playing as {color}.\n"
        "Use analyze_opening_repertoire to get statistics, then:\n"
        "1. Identify openings with a win rate below 40%.\n"
        "2. Use fetch_cloud_eval to evaluate typical positions from weak openings.\n"
        "3. Suggest alternative lines or improvements.\n"
        "Provide a structured report with ECO codes, win rates, and recommendations."
    )
    return GetPromptResult(
        description=f"Opening repertoire audit for {username} as {color}",
        messages=[PromptMessage(role="user", content=TextContent(type="text", text=text))],
    )
