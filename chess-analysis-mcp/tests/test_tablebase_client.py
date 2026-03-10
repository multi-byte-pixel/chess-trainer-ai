"""Tests for Tablebase client."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

_SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(_SRC))

from data.tablebase_client import (
    TablebaseClient,
    _parse_tablebase_response,
    _parse_mainline_response,
)


class TestParseTablebaseResponse:
    def test_parses_win_position(self):
        data = {
            "category": "win",
            "dtz": 5,
            "dtm": 12,
            "checkmate": False,
            "stalemate": False,
            "moves": [
                {
                    "uci": "e3e4",
                    "san": "e4",
                    "category": "loss",
                    "dtz": -4,
                    "dtm": -11,
                    "zeroing": True,
                    "checkmate": False,
                    "stalemate": False,
                },
            ],
        }
        result = _parse_tablebase_response(data)
        assert result["category"] == "win"
        assert result["dtz"] == 5
        assert result["dtm"] == 12
        assert len(result["moves"]) == 1
        assert result["moves"][0]["uci"] == "e3e4"

    def test_handles_draw(self):
        data = {
            "category": "draw",
            "dtz": 0,
            "dtm": None,
            "checkmate": False,
            "stalemate": False,
            "moves": [],
        }
        result = _parse_tablebase_response(data)
        assert result["category"] == "draw"
        assert result["moves"] == []


class TestParseMainlineResponse:
    def test_parses_mainline(self):
        data = {
            "winner": "w",
            "dtz": 5,
            "mainline": [
                {"uci": "e3e4", "san": "e4", "dtz": 4},
                {"uci": "e6e5", "san": "Ke5", "dtz": -3},
            ],
        }
        result = _parse_mainline_response(data)
        assert result["winner"] == "w"
        assert len(result["mainline"]) == 2


class TestTablebaseClientInit:
    def test_has_expected_methods(self):
        assert hasattr(TablebaseClient, "probe_position")
        assert hasattr(TablebaseClient, "mainline")
