"""Tests for new MCP tool modules (explorer, comparison, opening, annotation, puzzle, endgame)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(_SRC))

from data.models import AnalysisLine, AnalysisResult


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_analysis_result(
    fen: str = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
) -> AnalysisResult:
    return AnalysisResult(
        fen=fen,
        depth=20,
        lines=[
            AnalysisLine(
                depth=20, seldepth=25, cp=25, mate=None,
                pv="e7e5 g1f3 b8c6", multipv_rank=1,
            ),
        ],
        elapsed_ms=150.0,
    )


def _make_mock_cache():
    from data.storage import RedisCache

    cache = RedisCache.__new__(RedisCache)
    cache._url = "redis://localhost"
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.setex = AsyncMock()
    mock_client.delete = AsyncMock()
    cache._client = mock_client
    return cache


# ---------------------------------------------------------------------------
# Explorer tools
# ---------------------------------------------------------------------------

class TestExplorePosition:
    @pytest.mark.asyncio
    async def test_returns_moves_on_hit(self):
        from mcp_server.tools.explorer_tools import explore_position

        mock_chessdb = AsyncMock()
        mock_chessdb.query_all = AsyncMock(return_value={
            "status": "ok",
            "moves": [
                {"uci": "e2e4", "san": "e4", "score": 25, "rank": 1, "note": "", "winrate": 0.54},
            ],
            "fen": "startpos",
        })
        cache = _make_mock_cache()

        result = await explore_position(
            {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"},
            mock_chessdb,
            cache,
        )
        assert result["status"] == "ok"
        assert len(result["moves"]) == 1

    @pytest.mark.asyncio
    async def test_returns_not_found_on_miss(self):
        from mcp_server.tools.explorer_tools import explore_position

        mock_chessdb = AsyncMock()
        mock_chessdb.query_all = AsyncMock(return_value=None)
        cache = _make_mock_cache()
        # Patch the helper to return None
        with patch("mcp_server.tools.explorer_tools._get_chessdb_cached", return_value=None):
            result = await explore_position({"fen": "some_fen"}, mock_chessdb, cache)
            assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# Comparison tools
# ---------------------------------------------------------------------------

class TestCompareThreeSources:
    @pytest.mark.asyncio
    async def test_full_agreement(self):
        from mcp_server.tools.comparison_tools import compare_three_sources

        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"

        mock_engine = AsyncMock()
        mock_engine.analyze = AsyncMock(return_value=_make_analysis_result(fen))

        mock_lichess = AsyncMock()
        mock_lichess.get_cloud_eval = AsyncMock(return_value=None)

        mock_chessdb = AsyncMock()
        mock_chessdb.query_all = AsyncMock(return_value=None)

        cache = _make_mock_cache()

        # Patch the cached helpers to return expected data
        with patch("mcp_server.tools.comparison_tools._get_cloud_eval_cached", return_value={
            "evaluations": [{"pv": "e7e5 g1f3", "cp": 25}],
        }), patch("mcp_server.tools.comparison_tools._get_chessdb_cached", return_value={
            "moves": [{"uci": "e7e5", "score": 20}],
        }):
            result = await compare_three_sources(
                {"fen": fen}, mock_engine, mock_lichess, mock_chessdb, cache
            )

            assert result["consensus"] == "full_agreement"
            assert result["stockfish"]["best_move"] == "e7e5"


# ---------------------------------------------------------------------------
# Puzzle generation tools
# ---------------------------------------------------------------------------

class TestPuzzleGeneration:
    @pytest.mark.asyncio
    async def test_empty_pgn_returns_error(self):
        from mcp_server.tools.puzzle_tools import generate_puzzles_from_game

        mock_engine = AsyncMock()
        result = await generate_puzzles_from_game({"pgn": ""}, mock_engine)
        assert "error" in result or result.get("puzzles") == []


# ---------------------------------------------------------------------------
# Endgame tools
# ---------------------------------------------------------------------------

class TestProbeTablebase:
    @pytest.mark.asyncio
    async def test_too_many_pieces(self):
        from mcp_server.tools.endgame_tools import probe_tablebase

        mock_tablebase = AsyncMock()
        cache = _make_mock_cache()

        # Starting position has > 7 pieces
        result = await probe_tablebase(
            {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"},
            mock_tablebase,
            cache,
        )
        assert result["available"] is False

    @pytest.mark.asyncio
    async def test_valid_endgame_position(self):
        from mcp_server.tools.endgame_tools import probe_tablebase

        mock_tablebase = AsyncMock()
        mock_tablebase.probe_position = AsyncMock(return_value={
            "category": "win",
            "dtz": 5,
            "dtm": 12,
            "checkmate": False,
            "stalemate": False,
            "moves": [],
        })
        cache = _make_mock_cache()

        # KPK position (3 pieces)
        result = await probe_tablebase(
            {"fen": "8/8/4k3/8/4K3/4P3/8/8 w - - 0 1"},
            mock_tablebase,
            cache,
        )
        assert result["available"] is True
        assert result["category"] == "win"


# ---------------------------------------------------------------------------
# New models
# ---------------------------------------------------------------------------

class TestNewModels:
    def test_chessdb_move_model(self):
        from data.models import ChessDBMove

        m = ChessDBMove(uci="e2e4", san="e4", score=25, rank=1)
        assert m.uci == "e2e4"
        assert m.score == 25

    def test_tablebase_result_model(self):
        from data.models import TablebaseResult

        r = TablebaseResult(fen="test", category="win", dtz=5)
        assert r.category == "win"
        assert r.dtm is None

    def test_generated_puzzle_model(self):
        from data.models import GeneratedPuzzle

        p = GeneratedPuzzle(
            fen="test", solution_uci=["e2e4", "e7e5"],
            themes=["fork"], difficulty="medium",
        )
        assert p.difficulty == "medium"
        assert len(p.solution_uci) == 2
