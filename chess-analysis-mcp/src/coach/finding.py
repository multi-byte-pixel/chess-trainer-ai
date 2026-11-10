"""Finding: one engine judgement about one move, in a form an LLM can cite.

A Finding is the ground truth that explanations are checked against. It is
built from the existing ``BlunderInfo`` produced by
``PositionAnalyzer.find_blunders`` and never edited by hand.

Units and conventions
=====================
* ``loss`` is in pawns from the moving side's perspective and is always >= 0.
* Mate scores use a 30,000 cp sentinel upstream, so a raw mate swing would
  read as a 300-pawn loss. Those losses are capped at ``MAX_LOSS_PAWNS`` and
  flagged with ``mate_involved`` so numeric claims about them can be skipped
  rather than compared against a meaningless number.
* Moves are stored as UCI (what the engine returns) and SAN (what people and
  LLMs write). SAN is derived from the FEN; an illegal move raises.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Optional

import chess

from chess_engine.position_analyzer import classify_cp_loss
from data.models import BlunderInfo

MATE_SENTINEL_CP = 30_000
MAX_LOSS_PAWNS = 10.0

CLASSIFICATIONS = ("blunder", "mistake", "inaccuracy", "ok")


def _san(fen: str, uci: str) -> str:
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    if move not in board.legal_moves:
        raise ValueError(f"{uci} is not legal in {fen}")
    return board.san(move)


def _is_mate_score(cp: Optional[int]) -> bool:
    return cp is not None and abs(cp) >= MATE_SENTINEL_CP


@dataclass(frozen=True)
class Finding:
    id: str
    game_id: str
    ply: int
    player: str  # "white" | "black"
    fen: str  # position before the move
    played_uci: str
    played_san: str
    best_uci: str
    best_san: str
    loss: float  # pawns, >= 0
    classification: str
    mate_involved: bool
    engine: str
    engine_version: str
    depth: int
    pv: list[str] = field(default_factory=list)  # UCI, starting with best move

    def __post_init__(self) -> None:
        if self.loss < 0:
            raise ValueError(f"loss must be >= 0, got {self.loss}")
        if self.classification not in CLASSIFICATIONS:
            raise ValueError(f"unknown classification {self.classification!r}")
        if self.player not in ("white", "black"):
            raise ValueError(f"player must be white or black, got {self.player!r}")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "Finding":
        return cls(**json.loads(text))


def finding_id(game_id: str, ply: int) -> str:
    """Stable id: the same game and ply always give the same id."""
    return f"{game_id}:ply{ply}"


def from_blunder(
    blunder: BlunderInfo,
    *,
    game_id: str,
    engine_version: str,
    depth: int,
    pv: Optional[list[str]] = None,
    engine: str = "stockfish",
) -> Finding:
    mate = _is_mate_score(blunder.best_cp) or _is_mate_score(blunder.played_cp)
    loss = min(max(blunder.cp_loss, 0) / 100.0, MAX_LOSS_PAWNS)
    # Re-derive the label from cp so Finding and analyzer cannot drift apart.
    classification = classify_cp_loss(max(blunder.cp_loss, 0))
    return Finding(
        id=finding_id(game_id, blunder.ply),
        game_id=game_id,
        ply=blunder.ply,
        player=blunder.color,
        fen=blunder.fen_before,
        played_uci=blunder.played_move,
        played_san=_san(blunder.fen_before, blunder.played_move),
        best_uci=blunder.best_move,
        best_san=_san(blunder.fen_before, blunder.best_move),
        loss=loss,
        classification=classification,
        mate_involved=mate,
        engine=engine,
        engine_version=engine_version,
        depth=depth,
        pv=list(pv) if pv else [blunder.best_move],
    )
