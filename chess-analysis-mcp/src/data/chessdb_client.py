"""ChessDB API client with async httpx and retry logic.

ChessDB (chessdb.cn) provides a crowd-sourced chess analysis database with
billions of positions.  This client wraps its HTTP/JSON API for use by MCP
tools.

Network note – allowlisting
----------------------------
ChessDB is hosted at ``chessdb.cn``.  If your CI runner or production host
blocks outbound traffic by default you must allowlist the following:

* **Domain:** ``chessdb.cn``
* **Port:** ``443`` (HTTPS)
* **IP (as of 2024):** resolve ``chessdb.cn`` – IPs may rotate behind a CDN,
  so prefer domain-based rules.

AWS-specific allow-listing:
  1. **Security Group** – add an outbound rule for HTTPS (TCP 443) to
     ``0.0.0.0/0`` (or lock down to the resolved IPs).
  2. **NACL** – ensure the subnet NACL allows outbound 443 and ephemeral
     return traffic (1024-65535).
  3. **NAT Gateway** – if the ECS task runs in a private subnet, route
     outbound traffic through a NAT Gateway with internet access.
  4. **VPC Endpoint (optional)** – not applicable here since ChessDB is a
     public API, but keep this in mind for AWS-internal services.

For GitHub Actions CI, add a step that verifies connectivity::

    - name: Verify ChessDB connectivity
      run: curl -sf https://chessdb.cn/cdb_api_health || echo "ChessDB unreachable – skipping integration tests"

Environment variables
---------------------
``CHESSDB_API_URL``
    Base URL for the ChessDB API.  Default: ``https://chessdb.cn``

``CHESSDB_REQUEST_TIMEOUT``
    Request timeout in seconds.  Default: ``30``
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://chessdb.cn"


def _should_retry(exc: BaseException) -> bool:
    """Retry on 429 / 5xx responses or connection errors."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


class ChessDBClient:
    """Async client for the ChessDB (chessdb.cn) API.

    ChessDB provides:
    * **Query best move** – server-side best move for a FEN.
    * **Query all moves** – scored move list for a FEN.
    * **Queue position** – request analysis of an unvisited position.
    * **Query PV** – principal variation from a position.

    Usage::

        async with ChessDBClient() as cdb:
            result = await cdb.query_all(fen)
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE,
        timeout: float = 30.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "ChessDBClient":
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
    async def query_all(self, fen: str) -> dict[str, Any]:
        """Query all scored moves for a position.

        Returns a dict with keys ``status`` and ``moves`` (list of move dicts
        each containing ``uci``, ``san``, ``score``, ``rank``, ``note``, etc.).
        """
        params = {"action": "queryall", "board": fen, "json": 1}
        response = await self._client.get("/cdb", params=params)
        response.raise_for_status()
        data = response.json()
        return _parse_query_all(data)

    @retry(
        retry=retry_if_exception(_should_retry),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def query_best(self, fen: str) -> dict[str, Any]:
        """Query the single best move for a position.

        Returns a dict with ``status``, ``move`` (UCI), ``score``, and
        ``depth``.
        """
        params = {"action": "querybest", "board": fen, "json": 1}
        response = await self._client.get("/cdb", params=params)
        response.raise_for_status()
        return _parse_query_best(response.json())

    @retry(
        retry=retry_if_exception(_should_retry),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def query_pv(self, fen: str) -> dict[str, Any]:
        """Query the principal variation from a position.

        Returns ``status`` and ``pv`` (space-separated UCI moves).
        """
        params = {"action": "querypv", "board": fen, "json": 1}
        response = await self._client.get("/cdb", params=params)
        response.raise_for_status()
        return _parse_query_pv(response.json())

    @retry(
        retry=retry_if_exception(_should_retry),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def queue_position(self, fen: str) -> dict[str, Any]:
        """Request server-side analysis of a position not yet in the DB.

        Returns ``status`` indicating whether the position was queued.
        """
        params = {"action": "queue", "board": fen, "json": 1}
        response = await self._client.get("/cdb", params=params)
        response.raise_for_status()
        data = response.json()
        return {"status": data.get("status", "unknown")}

    @retry(
        retry=retry_if_exception(_should_retry),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def query_search(self, fen: str) -> dict[str, Any]:
        """Request a server-side search/analysis for a position.

        Returns ``status`` and evaluation details.
        """
        params = {"action": "querysearch", "board": fen, "json": 1}
        response = await self._client.get("/cdb", params=params)
        response.raise_for_status()
        return response.json()


# ------------------------------------------------------------------
# Parsers
# ------------------------------------------------------------------


def _parse_query_all(data: dict[str, Any]) -> dict[str, Any]:
    """Parse the queryall response into a standardised dict."""
    status = data.get("status", "unknown")
    raw_moves = data.get("moves", [])
    moves: list[dict[str, Any]] = []
    for m in raw_moves:
        moves.append({
            "uci": m.get("uci", ""),
            "san": m.get("san", ""),
            "score": m.get("score"),
            "rank": m.get("rank"),
            "note": m.get("note", ""),
            "winrate": m.get("winrate"),
        })
    return {"status": status, "moves": moves, "fen": data.get("fen", "")}


def _parse_query_best(data: dict[str, Any]) -> dict[str, Any]:
    """Parse the querybest response."""
    return {
        "status": data.get("status", "unknown"),
        "move": data.get("move", ""),
        "score": data.get("score"),
        "depth": data.get("depth"),
    }


def _parse_query_pv(data: dict[str, Any]) -> dict[str, Any]:
    """Parse the querypv response."""
    pv_raw = data.get("pv", "")
    return {
        "status": data.get("status", "unknown"),
        "pv": pv_raw if isinstance(pv_raw, str) else " ".join(pv_raw),
        "score": data.get("score"),
        "depth": data.get("depth"),
    }
