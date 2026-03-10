"""Tests for MCP tool handlers."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src is on the path
_SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(_SRC))

from data.models import (
    AnalysisLine,
    AnalysisResult,
    CloudEvalEntry,
    CloudEvalResult,
    Game,
    PuzzleActivity,
)
from data.storage import RedisCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_cache() -> RedisCache:
    """Return a RedisCache with a mocked Redis client."""
    cache = RedisCache.__new__(RedisCache)
    cache._url = "redis://localhost"
    cache._client = None
    return cache


def _make_mock_cache(data: dict | None = None) -> RedisCache:
    """Return a cache that always returns None (cache miss)."""
    cache = _make_cache()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.setex = AsyncMock()
    mock_client.delete = AsyncMock()
    cache._client = mock_client
    return cache


def _make_game(game_id: str = "abc123") -> Game:
    return Game(
        id=game_id,
        username="testuser",
        pgn="1. e4 e5 *",
        rated=True,
        perf_type="blitz",
        color="white",
        result="win",
        opponent_rating=1500,
        player_rating=1520,
        played_at=None,
        opening_eco="C50",
        opening_name="Italian Game",
    )


def _make_puzzle() -> PuzzleActivity:
    return PuzzleActivity(
        puzzle_id="pzl001",
        username="testuser",
        rating=1600,
        rating_diff=5,
        solved=True,
        played_at=None,
        themes=["fork", "middlegame"],
        fen="r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1",
    )


def _make_cloud_eval() -> CloudEvalResult:
    return CloudEvalResult(
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        evaluations=[
            CloudEvalEntry(depth=30, nodes=5000000, cp=25, mate=None, pv="e7e5 g1f3 b8c6"),
            CloudEvalEntry(depth=30, nodes=4000000, cp=15, mate=None, pv="c7c5 g1f3 d7d6"),
        ],
        knodes=9000,
    )


def _make_analysis_result(fen: str = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1") -> AnalysisResult:
    return AnalysisResult(
        fen=fen,
        depth=20,
        lines=[
            AnalysisLine(depth=20, seldepth=25, cp=25, mate=None, pv="e7e5 g1f3 b8c6", multipv_rank=1),
        ],
        elapsed_ms=150.0,
    )


# ---------------------------------------------------------------------------
# fetch_cloud_eval
# ---------------------------------------------------------------------------


class TestFetchCloudEval:
    @pytest.mark.asyncio
    async def test_returns_evaluations_on_hit(self):
        from mcp_server.tools.analysis_tools import fetch_cloud_eval

        mock_client = AsyncMock()
        mock_client.get_cloud_eval = AsyncMock(return_value=_make_cloud_eval())
        cache = _make_mock_cache()

        result = await fetch_cloud_eval(
            {"fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"},
            mock_client,
            cache,
        )

        assert result["available"] is True
        assert len(result["evaluations"]) == 2
        assert result["evaluations"][0]["cp"] == 25

    @pytest.mark.asyncio
    async def test_returns_unavailable_on_miss(self):
        from mcp_server.tools.analysis_tools import fetch_cloud_eval

        mock_client = AsyncMock()
        mock_client.get_cloud_eval = AsyncMock(return_value=None)
        cache = _make_mock_cache()

        result = await fetch_cloud_eval({"fen": "8/8/8/8/8/8/8/k6K w - - 0 1"}, mock_client, cache)

        assert result["available"] is False
        assert result["evaluations"] == []

    @pytest.mark.asyncio
    async def test_uses_cache_on_second_call(self):
        from mcp_server.tools.analysis_tools import fetch_cloud_eval

        mock_client = AsyncMock()
        mock_client.get_cloud_eval = AsyncMock(return_value=_make_cloud_eval())

        # First call populates cache
        cache = _make_mock_cache()
        await fetch_cloud_eval({"fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"}, mock_client, cache)

        # Simulate cached response
        cached_data = {
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "evaluations": [{"depth": 30, "nodes": 5000000, "cp": 25, "mate": None, "pv": "e7e5 g1f3 b8c6"}],
            "knodes": 9000,
        }
        cache._client.get = AsyncMock(return_value=json.dumps(cached_data))
        result = await fetch_cloud_eval(
            {"fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"},
            mock_client,
            cache,
        )
        assert result["available"] is True
        # API should only have been called once
        mock_client.get_cloud_eval.assert_called_once()


# ---------------------------------------------------------------------------
# compare_position_vs_cloud
# ---------------------------------------------------------------------------


class TestComparePositionVsCloud:
    @pytest.mark.asyncio
    async def test_agreement_when_moves_match(self):
        from mcp_server.tools.analysis_tools import compare_position_vs_cloud

        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"

        mock_engine = AsyncMock()
        mock_engine.analyze = AsyncMock(return_value=_make_analysis_result(fen))

        mock_client = AsyncMock()
        cloud = _make_cloud_eval()
        mock_client.get_cloud_eval = AsyncMock(return_value=cloud)
        cache = _make_mock_cache()

        result = await compare_position_vs_cloud(
            {"fen": fen, "local_depth": 20, "multi_pv": 2},
            mock_engine,
            mock_client,
            cache,
        )

        assert "local_eval" in result
        assert "cloud_eval" in result
        assert "agreement" in result
        assert "novelty_score" in result

    @pytest.mark.asyncio
    async def test_no_cloud_eval_available(self):
        from mcp_server.tools.analysis_tools import compare_position_vs_cloud

        fen = "8/8/8/8/8/8/8/k6K w - - 0 1"
        mock_engine = AsyncMock()
        mock_engine.analyze = AsyncMock(return_value=_make_analysis_result(fen))

        mock_client = AsyncMock()
        mock_client.get_cloud_eval = AsyncMock(return_value=None)
        cache = _make_mock_cache()

        result = await compare_position_vs_cloud({"fen": fen}, mock_engine, mock_client, cache)

        assert result["cloud_eval"] is None
        assert result["agreement"] is None


# ---------------------------------------------------------------------------
# annotate_game_with_cloud_eval
# ---------------------------------------------------------------------------


class TestAnnotateGameWithCloudEval:
    SIMPLE_PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 *"

    @pytest.mark.asyncio
    async def test_annotates_positions(self):
        from mcp_server.tools.analysis_tools import annotate_game_with_cloud_eval

        mock_engine = AsyncMock()
        mock_engine.analyze = AsyncMock(return_value=_make_analysis_result())

        mock_client = AsyncMock()
        mock_client.get_cloud_eval = AsyncMock(return_value=_make_cloud_eval())
        cache = _make_mock_cache()

        result = await annotate_game_with_cloud_eval(
            {"pgn": self.SIMPLE_PGN, "max_cloud_queries": 3, "sample_strategy": "every_move"},
            mock_engine,
            mock_client,
            cache,
        )

        assert "positions" in result
        assert len(result["positions"]) <= 3
        for pos in result["positions"]:
            assert "fen" in pos
            assert "local_eval" in pos
            assert "cloud_eval" in pos

    @pytest.mark.asyncio
    async def test_invalid_pgn_returns_error(self):
        from mcp_server.tools.analysis_tools import annotate_game_with_cloud_eval

        mock_engine = AsyncMock()
        mock_client = AsyncMock()
        cache = _make_mock_cache()

        result = await annotate_game_with_cloud_eval(
            {"pgn": ""},
            mock_engine,
            mock_client,
            cache,
        )

        assert "error" in result or result.get("positions") == []


# ---------------------------------------------------------------------------
# fetch_lichess_games
# ---------------------------------------------------------------------------


class TestFetchLichessGames:
    @pytest.mark.asyncio
    async def test_returns_games(self):
        from mcp_server.tools.game_tools import fetch_lichess_games

        mock_client = AsyncMock()
        mock_client.get_games = AsyncMock(return_value=[_make_game()])
        cache = _make_mock_cache()

        result = await fetch_lichess_games({"username": "testuser"}, mock_client, cache)

        assert "games" in result
        assert len(result["games"]) == 1
        assert result["games"][0]["id"] == "abc123"

    @pytest.mark.asyncio
    async def test_uses_cache(self):
        from mcp_server.tools.game_tools import fetch_lichess_games

        from dataclasses import asdict

        cached_games = [asdict(_make_game())]
        mock_client = AsyncMock()
        cache = _make_mock_cache()
        cache._client.get = AsyncMock(return_value=json.dumps(cached_games))

        result = await fetch_lichess_games({"username": "testuser"}, mock_client, cache)

        assert result["source"] == "cache"
        mock_client.get_games.assert_not_called()
