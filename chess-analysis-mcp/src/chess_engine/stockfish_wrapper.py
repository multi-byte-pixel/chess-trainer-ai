"""Async wrapper around Stockfish via python-chess."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import chess
import chess.engine

from data.models import AnalysisLine, AnalysisResult
from utils.config import get_settings
from utils.metrics import Timer

logger = logging.getLogger(__name__)

_MATE_SCORE_CP = 30_000  # sentinel centipawn value for mate


def _score_to_cp(score: chess.engine.Score) -> tuple[Optional[int], Optional[int]]:
    """Convert a python-chess Score to (cp, mate) pair."""
    if score.is_mate():
        mate = score.mate()
        cp = None
    else:
        cp = score.score()
        mate = None
    return cp, mate


class StockfishEngine:
    """Async Stockfish wrapper using python-chess engine protocol."""

    def __init__(self, path: Optional[str] = None) -> None:
        settings = get_settings()
        self._path = path or settings.stockfish_path
        self._threads = settings.stockfish_threads
        self._hash_mb = settings.stockfish_hash_mb
        self._transport: Optional[asyncio.SubprocessTransport] = None
        self._engine: Optional[chess.engine.UciProtocol] = None

    async def start(self) -> None:
        """Start the Stockfish process."""
        self._transport, self._engine = await chess.engine.popen_uci(self._path)
        await self._engine.configure(
            {"Threads": self._threads, "Hash": self._hash_mb}
        )
        logger.info("Stockfish started at %s", self._path)

    async def stop(self) -> None:
        """Stop the Stockfish process."""
        if self._engine:
            await self._engine.quit()
            self._engine = None
            self._transport = None

    async def __aenter__(self) -> "StockfishEngine":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze(
        self,
        fen: str,
        depth: int = 20,
        multipv: int = 1,
        time_limit: Optional[float] = None,
    ) -> AnalysisResult:
        """
        Analyse a position and return an AnalysisResult.

        Args:
            fen: FEN string of the position.
            depth: Analysis depth (ignored when time_limit is set exclusively).
            multipv: Number of principal variations.
            time_limit: Wall-clock time in seconds (overrides depth when provided).
        """
        if not self._engine:
            raise RuntimeError("Engine not started. Call start() first.")

        try:
            board = chess.Board(fen)
        except ValueError as exc:
            logger.error("Invalid FEN: %s – %s", fen, exc)
            return AnalysisResult(fen=fen, depth=0, lines=[], elapsed_ms=0.0)

        limit = chess.engine.Limit(
            time=time_limit if time_limit else None,
            depth=depth if not time_limit else None,
        )

        with Timer() as timer:
            info_list = await self._engine.analyse(board, limit, multipv=multipv)

        if not isinstance(info_list, list):
            info_list = [info_list]

        lines: list[AnalysisLine] = []
        for rank, info in enumerate(info_list, start=1):
            score_obj = info.get("score")
            if score_obj is None:
                continue
            # Normalise to white's perspective
            pov_score = score_obj.white()
            cp, mate = _score_to_cp(pov_score)
            pv_moves = info.get("pv", [])
            pv_str = " ".join(m.uci() for m in pv_moves)
            lines.append(
                AnalysisLine(
                    depth=info.get("depth", depth),
                    seldepth=info.get("seldepth"),
                    cp=cp,
                    mate=mate,
                    pv=pv_str,
                    multipv_rank=rank,
                )
            )

        effective_depth = lines[0].depth if lines else depth
        return AnalysisResult(
            fen=fen,
            depth=effective_depth,
            lines=lines,
            elapsed_ms=timer.elapsed_ms,
        )

    async def find_best_move(
        self,
        fen: str,
        time_limit: float = 1.0,
    ) -> Optional[str]:
        """Return the best move in UCI notation for the given position."""
        result = await self.analyze(fen, time_limit=time_limit, multipv=1)
        return result.best_move
