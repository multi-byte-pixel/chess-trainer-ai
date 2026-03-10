"""Main MCP server entry point."""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add src to the Python path when running directly
_SRC = Path(__file__).parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import mcp.server.stdio
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    Prompt,
    PromptArgument,
    ReadResourceResult,
    Resource,
    TextContent,
    TextResourceContents,
    Tool,
)

from chess_engine.stockfish_wrapper import StockfishEngine
from data.lichess_client import LichessClient
from data.storage import RedisCache
from mcp_server.prompts.analysis_prompts import (
    analyze_recent_games_prompt,
    opening_repertoire_audit_prompt,
    puzzle_performance_review_prompt,
)
from mcp_server.resources.data_resources import (
    get_analysis_report_resource,
    get_games_resource,
    get_puzzle_resource,
)
from mcp_server.tools.analysis_tools import (
    analyze_position,
    annotate_game_with_cloud_eval,
    compare_position_vs_cloud,
    compare_to_engine,
    fetch_cloud_eval,
)
from mcp_server.tools.game_tools import fetch_lichess_games, fetch_puzzle_activity
from mcp_server.tools.pattern_tools import detect_tactical_patterns
from mcp_server.tools.stats_tools import (
    aggregate_puzzle_statistics,
    analyze_opening_repertoire,
    generate_performance_report,
)
from mcp_server.tools.training_tools import generate_training_plan, suggest_puzzle_set
from utils.config import get_settings
from utils.logging import configure_logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

_TOOLS: list[Tool] = [
    Tool(
        name="fetch_lichess_games",
        description="Fetch recent games for a Lichess user.",
        inputSchema={
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Lichess username"},
                "max_games": {"type": "integer", "default": 20},
                "since": {"type": "integer", "description": "Unix timestamp ms"},
                "rated": {"type": "boolean"},
                "perf_type": {"type": "string"},
                "color": {"type": "string", "enum": ["white", "black"]},
            },
            "required": ["username"],
        },
    ),
    Tool(
        name="fetch_puzzle_activity",
        description="Fetch recent puzzle activity for a Lichess user.",
        inputSchema={
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "max_puzzles": {"type": "integer", "default": 50},
                "before": {"type": "integer", "description": "Unix timestamp ms"},
            },
            "required": ["username"],
        },
    ),
    Tool(
        name="analyze_position",
        description="Analyse a chess position with local Stockfish.",
        inputSchema={
            "type": "object",
            "properties": {
                "fen": {"type": "string", "description": "FEN string of the position"},
                "depth": {"type": "integer", "default": 20},
                "multipv": {"type": "integer", "default": 1},
                "time_limit": {"type": "number", "description": "Time limit in seconds"},
            },
            "required": ["fen"],
        },
    ),
    Tool(
        name="find_blunders",
        description="Find blunders and mistakes in a PGN game.",
        inputSchema={
            "type": "object",
            "properties": {
                "pgn": {"type": "string"},
                "depth": {"type": "integer", "default": 18},
            },
            "required": ["pgn"],
        },
    ),
    Tool(
        name="calculate_acpl",
        description="Calculate average centipawn loss for a game.",
        inputSchema={
            "type": "object",
            "properties": {
                "pgn": {"type": "string"},
                "depth": {"type": "integer", "default": 18},
            },
            "required": ["pgn"],
        },
    ),
    Tool(
        name="detect_tactical_patterns",
        description="Detect tactical patterns (fork, pin, skewer, etc.) in a position.",
        inputSchema={
            "type": "object",
            "properties": {
                "fen": {"type": "string"},
            },
            "required": ["fen"],
        },
    ),
    Tool(
        name="analyze_opening_repertoire",
        description="Analyse the opening repertoire for a user.",
        inputSchema={
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "max_games": {"type": "integer", "default": 100},
                "color": {"type": "string", "enum": ["white", "black"]},
            },
            "required": ["username"],
        },
    ),
    Tool(
        name="classify_endgame_type",
        description="Classify the endgame type for a position.",
        inputSchema={
            "type": "object",
            "properties": {
                "fen": {"type": "string"},
            },
            "required": ["fen"],
        },
    ),
    Tool(
        name="aggregate_puzzle_statistics",
        description="Aggregate puzzle statistics for a user.",
        inputSchema={
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "max_puzzles": {"type": "integer", "default": 200},
            },
            "required": ["username"],
        },
    ),
    Tool(
        name="generate_performance_report",
        description="Generate a high-level performance report for a user.",
        inputSchema={
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "max_games": {"type": "integer", "default": 50},
            },
            "required": ["username"],
        },
    ),
    Tool(
        name="compare_to_engine",
        description="Compare a played move to the engine's best move.",
        inputSchema={
            "type": "object",
            "properties": {
                "fen": {"type": "string"},
                "played_move": {"type": "string", "description": "UCI move notation"},
                "depth": {"type": "integer", "default": 20},
            },
            "required": ["fen", "played_move"],
        },
    ),
    Tool(
        name="generate_training_plan",
        description="Generate a personalised training plan for a user.",
        inputSchema={
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "max_games": {"type": "integer", "default": 30},
            },
            "required": ["username"],
        },
    ),
    Tool(
        name="suggest_puzzle_set",
        description="Suggest a puzzle theme set based on recent performance.",
        inputSchema={
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "max_puzzles": {"type": "integer", "default": 100},
            },
            "required": ["username"],
        },
    ),
    # Cloud Eval tools
    Tool(
        name="fetch_cloud_eval",
        description="Fetch Lichess Cloud Eval for a position (cached).",
        inputSchema={
            "type": "object",
            "properties": {
                "fen": {"type": "string"},
                "multi_pv": {"type": "integer", "default": 3},
                "variant": {"type": "string", "default": "standard"},
            },
            "required": ["fen"],
        },
    ),
    Tool(
        name="compare_position_vs_cloud",
        description="Compare local Stockfish evaluation with Lichess Cloud Eval.",
        inputSchema={
            "type": "object",
            "properties": {
                "fen": {"type": "string"},
                "local_depth": {"type": "integer", "default": 20},
                "multi_pv": {"type": "integer", "default": 3},
            },
            "required": ["fen"],
        },
    ),
    Tool(
        name="annotate_game_with_cloud_eval",
        description="Annotate game positions with local and cloud evaluations.",
        inputSchema={
            "type": "object",
            "properties": {
                "pgn": {"type": "string"},
                "sample_strategy": {
                    "type": "string",
                    "enum": ["every_move", "critical_only"],
                    "default": "every_move",
                },
                "max_cloud_queries": {"type": "integer", "default": 10},
                "local_depth": {"type": "integer", "default": 18},
                "multi_pv": {"type": "integer", "default": 1},
            },
            "required": ["pgn"],
        },
    ),
]

# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

_RESOURCES: list[Resource] = [
    Resource(
        uri="game://games/{username}",
        name="User Games",
        description="Recent games for a Lichess user.",
        mimeType="application/json",
    ),
    Resource(
        uri="puzzle://activity/{username}",
        name="Puzzle Activity",
        description="Recent puzzle activity for a Lichess user.",
        mimeType="application/json",
    ),
    Resource(
        uri="analysis://report/{username}/{period}",
        name="Analysis Report",
        description="Aggregated analysis report for a user and period.",
        mimeType="application/json",
    ),
]

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_PROMPTS: list[Prompt] = [
    Prompt(
        name="analyze-recent-games",
        description="Analyse recent games for a Lichess user.",
        arguments=[
            PromptArgument(name="username", description="Lichess username", required=True),
            PromptArgument(name="num_games", description="Number of games to analyse", required=False),
        ],
    ),
    Prompt(
        name="puzzle-performance-review",
        description="Review puzzle performance for a user.",
        arguments=[
            PromptArgument(name="username", description="Lichess username", required=True),
            PromptArgument(name="max_puzzles", description="Number of puzzles to review", required=False),
        ],
    ),
    Prompt(
        name="opening-repertoire-audit",
        description="Audit the opening repertoire for a user.",
        arguments=[
            PromptArgument(name="username", description="Lichess username", required=True),
            PromptArgument(name="color", description="Color to analyse (white/black)", required=False),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


def create_server(engine: StockfishEngine, client: LichessClient, cache: RedisCache) -> Server:
    """Create and configure the MCP server."""
    app = Server("chess-analysis-mcp")

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return _TOOLS

    @app.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        result = await _dispatch_tool(name, arguments, engine, client, cache)
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    @app.list_resources()
    async def list_resources() -> list[Resource]:
        return _RESOURCES

    @app.read_resource()
    async def read_resource(uri: str) -> str:
        return await _dispatch_resource(str(uri), client, cache)

    @app.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return _PROMPTS

    @app.get_prompt()
    async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
        args = arguments or {}
        return _dispatch_prompt(name, args)

    return app


# ---------------------------------------------------------------------------
# Dispatch helpers
# ---------------------------------------------------------------------------


async def _dispatch_tool(
    name: str,
    args: dict[str, Any],
    engine: StockfishEngine,
    client: LichessClient,
    cache: RedisCache,
) -> Any:
    from chess_engine.position_analyzer import PositionAnalyzer

    analyzer = PositionAnalyzer(engine)

    match name:
        case "fetch_lichess_games":
            return await fetch_lichess_games(args, client, cache)
        case "fetch_puzzle_activity":
            return await fetch_puzzle_activity(args, client, cache)
        case "analyze_position":
            return await analyze_position(args, engine)
        case "find_blunders":
            blunders = await analyzer.find_blunders(args["pgn"], depth=args.get("depth", 18))
            from dataclasses import asdict
            return {"blunders": [asdict(b) for b in blunders]}
        case "calculate_acpl":
            acpl = await analyzer.calculate_acpl(args["pgn"], depth=args.get("depth", 18))
            return {"acpl": acpl}
        case "detect_tactical_patterns":
            return await detect_tactical_patterns(args)
        case "analyze_opening_repertoire":
            return await analyze_opening_repertoire(args, client, cache)
        case "classify_endgame_type":
            classification = analyzer.classify_endgame(args["fen"])
            return {"fen": args["fen"], "endgame_type": classification}
        case "aggregate_puzzle_statistics":
            return await aggregate_puzzle_statistics(args, client, cache)
        case "generate_performance_report":
            return await generate_performance_report(args, client, cache)
        case "compare_to_engine":
            return await compare_to_engine(args, engine)
        case "generate_training_plan":
            return await generate_training_plan(args, client, engine, cache)
        case "suggest_puzzle_set":
            return await suggest_puzzle_set(args, client, cache)
        case "fetch_cloud_eval":
            return await fetch_cloud_eval(args, client, cache)
        case "compare_position_vs_cloud":
            return await compare_position_vs_cloud(args, engine, client, cache)
        case "annotate_game_with_cloud_eval":
            return await annotate_game_with_cloud_eval(args, engine, client, cache)
        case _:
            return {"error": f"Unknown tool: {name}"}


async def _dispatch_resource(uri: str, client: LichessClient, cache: RedisCache) -> str:
    import re

    if m := re.match(r"game://games/(.+)", uri):
        return await get_games_resource(m.group(1), client, cache)
    if m := re.match(r"puzzle://activity/(.+)", uri):
        return await get_puzzle_resource(m.group(1), client, cache)
    if m := re.match(r"analysis://report/([^/]+)/(.+)", uri):
        return await get_analysis_report_resource(m.group(1), m.group(2), client, cache)
    return json.dumps({"error": f"Unknown resource URI: {uri}"})


def _dispatch_prompt(name: str, args: dict[str, str]) -> GetPromptResult:
    match name:
        case "analyze-recent-games":
            return analyze_recent_games_prompt(
                args["username"],
                num_games=int(args.get("num_games", 10)),
            )
        case "puzzle-performance-review":
            return puzzle_performance_review_prompt(
                args["username"],
                max_puzzles=int(args.get("max_puzzles", 50)),
            )
        case "opening-repertoire-audit":
            return opening_repertoire_audit_prompt(
                args["username"],
                color=args.get("color", "white"),
            )
        case _:
            from mcp.types import PromptMessage, TextContent
            return GetPromptResult(
                description="Unknown prompt",
                messages=[PromptMessage(role="user", content=TextContent(type="text", text=f"Unknown prompt: {name}"))],
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _run() -> None:
    configure_logging()
    settings = get_settings()
    logger.info("Starting chess-analysis-mcp server on port %d", settings.mcp_port)

    engine = StockfishEngine()
    client = LichessClient(token=settings.lichess_token)
    cache = RedisCache(settings.redis_url)

    await engine.start()
    await cache.connect()

    try:
        server = create_server(engine, client, cache)
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="chess-analysis-mcp",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities={},
                    ),
                ),
            )
    finally:
        await engine.stop()
        await client.close()
        await cache.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
