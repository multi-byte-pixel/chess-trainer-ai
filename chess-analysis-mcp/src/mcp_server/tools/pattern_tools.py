"""Pattern detection tool handlers."""
from __future__ import annotations

from typing import Any

from chess_engine.pattern_detector import detect_patterns


async def detect_tactical_patterns(args: dict[str, Any]) -> dict[str, Any]:
    """Detect tactical patterns in a given FEN position."""
    fen: str = args["fen"]
    patterns = detect_patterns(fen)
    active_patterns = [name for name, present in patterns.items() if present]
    return {
        "fen": fen,
        "patterns": patterns,
        "active_patterns": active_patterns,
    }
