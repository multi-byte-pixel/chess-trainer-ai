"""Opening preparation tool handlers using ChessDB.

Provides MCP tools for studying openings using ChessDB's
crowd-sourced opening data combined with Lichess game statistics.
"""
from __future__ import annotations

import io
import logging
from collections import Counter
from typing import Any, Optional

import chess
import chess.pgn

from data.chessdb_client import ChessDBClient
from data.lichess_client import LichessClient
from data.storage import RedisCache
from mcp_server.tools.explorer_tools import _get_chessdb_cached
from utils.config import get_settings

logger = logging.getLogger(__name__)


async def opening_explorer(
    args: dict[str, Any],
    chessdb_client: ChessDBClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Explore opening moves from a position using ChessDB.

    Given a FEN (defaults to starting position), returns the top moves
    with their ChessDB scores, ranks, and win-rates.
    """
    fen: str = args.get(
        "fen",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )

    data = await _get_chessdb_cached(fen, "queryall", chessdb_client, cache)
    if data is None:
        return {"fen": fen, "moves": [], "status": "not_found"}

    return {
        "fen": fen,
        "moves": data.get("moves", []),
        "status": data.get("status", "ok"),
    }


async def opening_line_analysis(
    args: dict[str, Any],
    chessdb_client: ChessDBClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Analyse a specific opening line using ChessDB evaluations.

    Accepts a sequence of UCI moves (or a PGN) and returns the
    ChessDB evaluation at each position along the line.
    """
    moves_uci: list[str] = args.get("moves", [])
    pgn_str: Optional[str] = args.get("pgn")

    # If PGN is provided, extract moves from it
    if pgn_str:
        try:
            game = chess.pgn.read_game(io.StringIO(pgn_str))
            if game:
                board = game.board()
                moves_uci = [m.uci() for m in game.mainline_moves()]
        except Exception as exc:
            return {"error": f"Failed to parse PGN: {exc}"}

    if not moves_uci:
        return {"error": "No moves provided. Supply 'moves' (UCI list) or 'pgn'."}

    board = chess.Board()
    positions: list[dict[str, Any]] = []

    for i, uci_move in enumerate(moves_uci):
        fen = board.fen()
        data = await _get_chessdb_cached(fen, "queryall", chessdb_client, cache)

        position_info: dict[str, Any] = {
            "move_number": board.fullmove_number,
            "move": uci_move,
            "fen": fen,
            "chessdb_status": "not_found",
            "top_moves": [],
            "played_move_rank": None,
            "played_move_score": None,
        }

        if data and data.get("moves"):
            position_info["chessdb_status"] = data.get("status", "ok")
            position_info["top_moves"] = data["moves"][:5]

            # Find where the played move ranks
            for rank, m in enumerate(data["moves"], 1):
                if m.get("uci") == uci_move:
                    position_info["played_move_rank"] = rank
                    position_info["played_move_score"] = m.get("score")
                    break

        positions.append(position_info)

        try:
            board.push_uci(uci_move)
        except ValueError as exc:
            position_info["error"] = f"Invalid move: {exc}"
            break

    return {"positions": positions, "total_moves": len(moves_uci)}


async def opening_repertoire_vs_chessdb(
    args: dict[str, Any],
    lichess_client: LichessClient,
    chessdb_client: ChessDBClient,
    cache: RedisCache,
) -> dict[str, Any]:
    """Compare a user's opening repertoire against ChessDB recommendations.

    Fetches the user's recent games, identifies their most-played
    openings, then checks how those lines score in ChessDB.
    """
    username: str = args["username"]
    max_games: int = args.get("max_games", 50)
    color: Optional[str] = args.get("color")

    games = await lichess_client.get_games(username, max_games=max_games, color=color)

    # Group by opening ECO
    opening_stats: dict[str, dict[str, Any]] = {}
    for g in games:
        eco = g.opening_eco or "Unknown"
        if eco not in opening_stats:
            opening_stats[eco] = {
                "eco": eco,
                "name": g.opening_name or "Unknown",
                "games": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
            }
        opening_stats[eco]["games"] += 1
        if g.result == "win":
            opening_stats[eco]["wins"] += 1
        elif g.result == "loss":
            opening_stats[eco]["losses"] += 1
        else:
            opening_stats[eco]["draws"] += 1

    # For top 5 openings, get ChessDB evaluation of the starting position
    sorted_openings = sorted(
        opening_stats.values(), key=lambda x: x["games"], reverse=True
    )[:5]

    for opening in sorted_openings:
        win_rate = opening["wins"] / opening["games"] if opening["games"] else 0
        opening["win_rate"] = round(win_rate * 100, 1)

    return {
        "username": username,
        "color": color,
        "total_games": len(games),
        "top_openings": sorted_openings,
    }
