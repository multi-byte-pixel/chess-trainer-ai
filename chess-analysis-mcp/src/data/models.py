"""Domain models / dataclasses for the chess analysis application."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Game:
    """Represents a Lichess game."""

    id: str
    username: str
    pgn: str
    rated: bool
    perf_type: str
    color: str
    result: str
    opponent_rating: Optional[int]
    player_rating: Optional[int]
    played_at: Optional[datetime]
    opening_eco: Optional[str] = None
    opening_name: Optional[str] = None


@dataclass
class PuzzleActivity:
    """Represents a single puzzle activity entry from Lichess."""

    puzzle_id: str
    username: str
    rating: int
    rating_diff: int
    solved: bool
    played_at: Optional[datetime]
    themes: list[str] = field(default_factory=list)
    fen: Optional[str] = None


@dataclass
class CloudEvalEntry:
    """A single evaluation line from the Lichess Cloud Eval API."""

    depth: int
    nodes: Optional[int]
    cp: Optional[int]
    mate: Optional[int]
    pv: str  # space-separated UCI moves


@dataclass
class CloudEvalResult:
    """Full result from the Lichess Cloud Eval API."""

    fen: str
    evaluations: list[CloudEvalEntry]
    knodes: Optional[int] = None


@dataclass
class AnalysisLine:
    """One PV line from the local Stockfish analysis."""

    depth: int
    seldepth: Optional[int]
    cp: Optional[int]
    mate: Optional[int]
    pv: str  # space-separated UCI moves
    multipv_rank: int = 1


@dataclass
class AnalysisResult:
    """Result from the StockfishEngine.analyze() call."""

    fen: str
    depth: int
    lines: list[AnalysisLine]
    elapsed_ms: float = 0.0

    @property
    def best_line(self) -> Optional[AnalysisLine]:
        return self.lines[0] if self.lines else None

    @property
    def best_move(self) -> Optional[str]:
        if self.best_line and self.best_line.pv:
            return self.best_line.pv.split()[0]
        return None


@dataclass
class BlunderInfo:
    """Information about a blunder detected in a game."""

    move_number: int
    ply: int
    color: str
    played_move: str
    best_move: str
    played_cp: Optional[int]
    best_cp: Optional[int]
    cp_loss: int
    fen_before: str
    fen_after: str
    classification: str  # blunder / mistake / inaccuracy


@dataclass
class ChessDBMove:
    """A single move entry from the ChessDB queryall response."""

    uci: str
    san: str
    score: Optional[int]
    rank: Optional[int]
    note: str = ""
    winrate: Optional[float] = None


@dataclass
class ChessDBResult:
    """Full result from a ChessDB query."""

    fen: str
    status: str
    moves: list[ChessDBMove] = field(default_factory=list)


@dataclass
class TablebaseResult:
    """Result from a Lichess Tablebase probe."""

    fen: str
    category: str  # win, loss, draw, cursed-win, blessed-loss
    dtz: Optional[int] = None  # Distance to Zeroing
    dtm: Optional[int] = None  # Distance to Mate
    checkmate: bool = False
    stalemate: bool = False


@dataclass
class GeneratedPuzzle:
    """A puzzle generated from game analysis."""

    fen: str
    solution_uci: list[str]  # sequence of UCI moves
    themes: list[str] = field(default_factory=list)
    difficulty: str = "unknown"  # easy, medium, hard
    source_game_id: Optional[str] = None
    cp_loss_trigger: Optional[int] = None  # cp loss that triggered the puzzle


@dataclass
class PerformanceSnapshot:
    """Aggregated performance data for a user over a period."""

    username: str
    period: str
    rating: Optional[int]
    games_played: int
    wins: int
    losses: int
    draws: int
    avg_acpl: Optional[float]
    puzzle_rating: Optional[int]
    puzzle_count: int
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
