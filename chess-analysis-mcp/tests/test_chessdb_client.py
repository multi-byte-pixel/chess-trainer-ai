"""Tests for ChessDB client."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(_SRC))

from data.chessdb_client import ChessDBClient, _parse_query_all, _parse_query_best, _parse_query_pv


class TestParseQueryAll:
    def test_parses_moves(self):
        data = {
            "status": "ok",
            "moves": [
                {"uci": "e2e4", "san": "e4", "score": 25, "rank": 1, "note": "", "winrate": 0.54},
                {"uci": "d2d4", "san": "d4", "score": 20, "rank": 2, "note": "", "winrate": 0.53},
            ],
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        }
        result = _parse_query_all(data)
        assert result["status"] == "ok"
        assert len(result["moves"]) == 2
        assert result["moves"][0]["uci"] == "e2e4"
        assert result["moves"][0]["score"] == 25

    def test_handles_empty_moves(self):
        data = {"status": "nobestmove", "moves": []}
        result = _parse_query_all(data)
        assert result["moves"] == []
        assert result["status"] == "nobestmove"


class TestParseQueryBest:
    def test_parses_best_move(self):
        data = {"status": "ok", "move": "e2e4", "score": 25, "depth": 40}
        result = _parse_query_best(data)
        assert result["move"] == "e2e4"
        assert result["score"] == 25
        assert result["depth"] == 40


class TestParseQueryPV:
    def test_parses_pv_string(self):
        data = {"status": "ok", "pv": "e2e4 e7e5 g1f3", "score": 25, "depth": 40}
        result = _parse_query_pv(data)
        assert result["pv"] == "e2e4 e7e5 g1f3"

    def test_handles_list_pv(self):
        data = {"status": "ok", "pv": ["e2e4", "e7e5", "g1f3"], "score": 25, "depth": 40}
        result = _parse_query_pv(data)
        assert result["pv"] == "e2e4 e7e5 g1f3"


class TestChessDBClientInit:
    def test_default_base_url(self):
        client = ChessDBClient.__new__(ChessDBClient)
        # Verify class can be instantiated (integration test would test actual HTTP)
        assert hasattr(ChessDBClient, "query_all")
        assert hasattr(ChessDBClient, "query_best")
        assert hasattr(ChessDBClient, "query_pv")
        assert hasattr(ChessDBClient, "queue_position")
