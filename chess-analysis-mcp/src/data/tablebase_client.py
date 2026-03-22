"""Lichess Tablebase client for endgame lookups.

Uses the Lichess Tablebase API (tablebase.lichess.ovh) which provides
Syzygy tablebase probes for positions with up to 7 pieces.

No authentication is required.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://tablebase.lichess.ovh"


def _should_retry(exc: BaseException) -> bool:
    """Retry on 429 / 5xx responses or connection errors."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


class TablebaseClient:
    """Async client for the Lichess Tablebase API.

    Endpoints:
    * ``/standard`` – Syzygy tablebase lookup for standard chess.
    * ``/atomic``, ``/antichess`` – variant tablebases (not used here).

    Usage::

        async with TablebaseClient() as tb:
            result = await tb.probe_position(fen)
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE,
        timeout: float = 15.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "TablebaseClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # API methods
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception(_should_retry),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def probe_position(self, fen: str) -> Optional[dict[str, Any]]:
        """Probe a standard chess position in the Syzygy tablebase.

        Returns ``None`` if the position has too many pieces or is not
        in the tablebase (HTTP 404).

        Otherwise returns a dict with:
        * ``category`` – "win", "loss", "draw", "cursed-win",
          "blessed-loss", or "maybe-win" / "maybe-loss".
        * ``dtz`` – Distance to Zeroing (half-moves).
        * ``dtm`` – Distance to Mate (if available, else ``None``).
        * ``moves`` – list of legal moves with their own evaluations.
        """
        response = await self._client.get("/standard", params={"fen": fen})
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        return _parse_tablebase_response(data)

    @retry(
        retry=retry_if_exception(_should_retry),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def mainline(self, fen: str) -> Optional[dict[str, Any]]:
        """Get the tablebase mainline (optimal play sequence) from a position.

        Returns ``None`` when not available; otherwise a dict with
        ``moves`` (list of UCI moves), ``winner``, and ``dtz``.
        """
        response = await self._client.get("/standard/mainline", params={"fen": fen})
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        return _parse_mainline_response(data)


# ------------------------------------------------------------------
# Parsers
# ------------------------------------------------------------------


def _parse_tablebase_response(data: dict[str, Any]) -> dict[str, Any]:
    """Parse the tablebase probe response."""
    moves = []
    for m in data.get("moves", []):
        moves.append({
            "uci": m.get("uci", ""),
            "san": m.get("san", ""),
            "category": m.get("category", "unknown"),
            "dtz": m.get("dtz"),
            "dtm": m.get("dtm"),
            "zeroing": m.get("zeroing", False),
            "checkmate": m.get("checkmate", False),
            "stalemate": m.get("stalemate", False),
        })
    return {
        "category": data.get("category", "unknown"),
        "dtz": data.get("dtz"),
        "dtm": data.get("dtm"),
        "checkmate": data.get("checkmate", False),
        "stalemate": data.get("stalemate", False),
        "moves": moves,
    }


def _parse_mainline_response(data: dict[str, Any]) -> dict[str, Any]:
    """Parse the mainline response."""
    mainline_moves = []
    for m in data.get("mainline", []):
        mainline_moves.append({
            "uci": m.get("uci", ""),
            "san": m.get("san", ""),
            "dtz": m.get("dtz"),
        })
    return {
        "winner": data.get("winner"),
        "dtz": data.get("dtz"),
        "mainline": mainline_moves,
    }
