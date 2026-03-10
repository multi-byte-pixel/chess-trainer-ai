"""Lichess API client with async httpx, retries and Cloud Eval support."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from data.models import CloudEvalEntry, CloudEvalResult, Game, PuzzleActivity

logger = logging.getLogger(__name__)

_BASE = "https://lichess.org"
_LICHESS_NDJSON = "application/x-ndjson"


def _should_retry(exc: BaseException) -> bool:
    """Retry on 429 / 5xx responses or connection errors."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


class LichessClient:
    """Async Lichess API client."""

    def __init__(self, token: str = "", timeout: float = 30.0) -> None:
        headers: dict[str, str] = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=_BASE,
            headers=headers,
            timeout=timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "LichessClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Games
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception(_should_retry),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def get_games(
        self,
        username: str,
        max_games: int = 20,
        since: Optional[int] = None,
        rated: Optional[bool] = None,
        perf_type: Optional[str] = None,
        color: Optional[str] = None,
    ) -> list[Game]:
        """Fetch games for a Lichess user as a list of Game objects."""
        params: dict[str, Any] = {
            "max": max_games,
            "pgnInJson": True,
            "opening": True,
            "clocks": False,
            "evals": False,
        }
        if since is not None:
            params["since"] = since
        if rated is not None:
            params["rated"] = str(rated).lower()
        if perf_type:
            params["perfType"] = perf_type
        if color:
            params["color"] = color

        response = await self._client.get(
            f"/api/games/user/{username}",
            params=params,
            headers={"Accept": _LICHESS_NDJSON},
        )
        response.raise_for_status()

        games: list[Game] = []
        for line in response.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                games.append(_parse_game(raw, username))
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Failed to parse game line: %s", exc)
        return games

    # ------------------------------------------------------------------
    # Puzzles
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception(_should_retry),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def get_puzzle_activity(
        self,
        username: str,
        max_puzzles: int = 50,
        before: Optional[int] = None,
    ) -> list[PuzzleActivity]:
        """Fetch puzzle activity for a Lichess user."""
        params: dict[str, Any] = {"max": max_puzzles}
        if before is not None:
            params["before"] = before

        response = await self._client.get(
            "/api/puzzle/activity",
            params=params,
            headers={"Accept": _LICHESS_NDJSON},
        )
        response.raise_for_status()

        puzzles: list[PuzzleActivity] = []
        for line in response.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                puzzles.append(_parse_puzzle(raw, username))
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Failed to parse puzzle line: %s", exc)
        return puzzles

    # ------------------------------------------------------------------
    # Cloud Eval
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception(_should_retry),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def get_cloud_eval(
        self,
        fen: str,
        multi_pv: int = 3,
        variant: str = "standard",
    ) -> Optional[CloudEvalResult]:
        """
        Fetch cloud evaluation for a position from Lichess.

        Returns None if the position is not in the cloud database (404).
        """
        params: dict[str, Any] = {
            "fen": fen,
            "multiPv": multi_pv,
        }
        if variant and variant != "standard":
            params["variant"] = variant

        response = await self._client.get("/api/cloud-eval", params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()

        data = response.json()
        return _parse_cloud_eval(data)


# ------------------------------------------------------------------
# Parsers
# ------------------------------------------------------------------


def _parse_game(raw: dict[str, Any], username: str) -> Game:
    players = raw.get("players", {})
    white = players.get("white", {})
    black = players.get("black", {})

    if white.get("user", {}).get("name", "").lower() == username.lower():
        color = "white"
        player_rating = white.get("rating")
        opponent_rating = black.get("rating")
    else:
        color = "black"
        player_rating = black.get("rating")
        opponent_rating = white.get("rating")

    winner = raw.get("winner")
    if winner is None:
        result = "draw"
    elif winner == color:
        result = "win"
    else:
        result = "loss"

    opening = raw.get("opening", {})
    played_at: Optional[datetime] = None
    ts = raw.get("createdAt")
    if ts:
        played_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

    return Game(
        id=raw["id"],
        username=username,
        pgn=raw.get("pgn", ""),
        rated=raw.get("rated", False),
        perf_type=raw.get("perf", ""),
        color=color,
        result=result,
        opponent_rating=opponent_rating,
        player_rating=player_rating,
        played_at=played_at,
        opening_eco=opening.get("eco"),
        opening_name=opening.get("name"),
    )


def _parse_puzzle(raw: dict[str, Any], username: str) -> PuzzleActivity:
    puzzle = raw.get("puzzle", {})
    played_at: Optional[datetime] = None
    ts = raw.get("date")
    if ts:
        played_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

    return PuzzleActivity(
        puzzle_id=puzzle.get("id", raw.get("id", "")),
        username=username,
        rating=puzzle.get("rating", 0),
        rating_diff=raw.get("puzzleRatingDiff", 0),
        solved=raw.get("win", False),
        played_at=played_at,
        themes=puzzle.get("themes", []),
        fen=puzzle.get("fen"),
    )


def _parse_cloud_eval(data: dict[str, Any]) -> CloudEvalResult:
    raw_pvs = data.get("pvs", [])
    evaluations: list[CloudEvalEntry] = []
    for pv in raw_pvs:
        evaluations.append(
            CloudEvalEntry(
                depth=pv.get("depth", 0),
                nodes=pv.get("nodes"),
                cp=pv.get("cp"),
                mate=pv.get("mate"),
                pv=pv.get("moves", ""),
            )
        )
    return CloudEvalResult(
        fen=data.get("fen", ""),
        evaluations=evaluations,
        knodes=data.get("knodes"),
    )
