"""PostgreSQL and Redis storage layer."""
from __future__ import annotations

import json
from typing import Any, Optional

import asyncpg
import redis.asyncio as aioredis

from utils.config import get_settings

# ---------------------------------------------------------------------------
# Redis cache
# ---------------------------------------------------------------------------


class RedisCache:
    """Simple async Redis cache wrapper."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        self._client = aioredis.from_url(self._url, decode_responses=True)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "RedisCache":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def get(self, key: str) -> Optional[Any]:
        """Return the cached value for *key*, or None if absent."""
        if not self._client:
            return None
        raw = await self._client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Cache *value* under *key* with *ttl* seconds expiry."""
        if not self._client:
            return
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await self._client.setex(key, ttl, serialized)

    async def delete(self, key: str) -> None:
        if self._client:
            await self._client.delete(key)


# ---------------------------------------------------------------------------
# PostgreSQL storage
# ---------------------------------------------------------------------------

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS games (
    id              TEXT PRIMARY KEY,
    username        TEXT NOT NULL,
    pgn             TEXT NOT NULL,
    rated           BOOLEAN NOT NULL DEFAULT FALSE,
    perf_type       TEXT,
    color           TEXT,
    result          TEXT,
    opponent_rating INTEGER,
    player_rating   INTEGER,
    opening_eco     TEXT,
    opening_name    TEXT,
    played_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS game_analysis (
    id              BIGSERIAL PRIMARY KEY,
    game_id         TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    username        TEXT NOT NULL,
    acpl            FLOAT,
    blunder_count   INTEGER DEFAULT 0,
    mistake_count   INTEGER DEFAULT 0,
    inaccuracy_count INTEGER DEFAULT 0,
    cloud_cp        INTEGER,
    cloud_best_move TEXT,
    analyzed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS puzzles (
    id          BIGSERIAL PRIMARY KEY,
    puzzle_id   TEXT NOT NULL,
    username    TEXT NOT NULL,
    rating      INTEGER,
    rating_diff INTEGER,
    solved      BOOLEAN NOT NULL DEFAULT FALSE,
    themes      TEXT[],
    fen         TEXT,
    played_at   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (puzzle_id, username, played_at)
);

CREATE TABLE IF NOT EXISTS performance_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    username        TEXT NOT NULL,
    period          TEXT NOT NULL,
    rating          INTEGER,
    games_played    INTEGER DEFAULT 0,
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    draws           INTEGER DEFAULT 0,
    avg_acpl        FLOAT,
    puzzle_rating   INTEGER,
    puzzle_count    INTEGER DEFAULT 0,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_games_username ON games (username);
CREATE INDEX IF NOT EXISTS idx_puzzles_username ON puzzles (username);
CREATE INDEX IF NOT EXISTS idx_snapshots_username_period ON performance_snapshots (username, period);
"""


class PostgresStorage:
    """Async PostgreSQL storage backend."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)
        async with self._pool.acquire() as conn:
            await conn.execute(_INIT_SQL)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def __aenter__(self) -> "PostgresStorage":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Games
    # ------------------------------------------------------------------

    async def upsert_game(self, game: Any) -> None:
        assert self._pool
        await self._pool.execute(
            """
            INSERT INTO games (id, username, pgn, rated, perf_type, color, result,
                               opponent_rating, player_rating, opening_eco, opening_name, played_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            ON CONFLICT (id) DO UPDATE SET
                pgn = EXCLUDED.pgn,
                opening_eco = EXCLUDED.opening_eco,
                opening_name = EXCLUDED.opening_name
            """,
            game.id, game.username, game.pgn, game.rated, game.perf_type,
            game.color, game.result, game.opponent_rating, game.player_rating,
            game.opening_eco, game.opening_name, game.played_at,
        )

    async def get_games(self, username: str, limit: int = 20) -> list[dict[str, Any]]:
        assert self._pool
        rows = await self._pool.fetch(
            "SELECT * FROM games WHERE username = $1 ORDER BY played_at DESC LIMIT $2",
            username, limit,
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Puzzles
    # ------------------------------------------------------------------

    async def upsert_puzzle(self, puzzle: Any) -> None:
        assert self._pool
        await self._pool.execute(
            """
            INSERT INTO puzzles (puzzle_id, username, rating, rating_diff, solved, themes, fen, played_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT (puzzle_id, username, played_at) DO NOTHING
            """,
            puzzle.puzzle_id, puzzle.username, puzzle.rating, puzzle.rating_diff,
            puzzle.solved, puzzle.themes, puzzle.fen, puzzle.played_at,
        )

    async def get_puzzles(self, username: str, limit: int = 50) -> list[dict[str, Any]]:
        assert self._pool
        rows = await self._pool.fetch(
            "SELECT * FROM puzzles WHERE username = $1 ORDER BY played_at DESC LIMIT $2",
            username, limit,
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    async def save_analysis(
        self,
        game_id: str,
        username: str,
        acpl: Optional[float] = None,
        blunder_count: int = 0,
        mistake_count: int = 0,
        inaccuracy_count: int = 0,
        cloud_cp: Optional[int] = None,
        cloud_best_move: Optional[str] = None,
    ) -> None:
        assert self._pool
        await self._pool.execute(
            """
            INSERT INTO game_analysis (game_id, username, acpl, blunder_count,
                mistake_count, inaccuracy_count, cloud_cp, cloud_best_move)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """,
            game_id, username, acpl, blunder_count, mistake_count, inaccuracy_count,
            cloud_cp, cloud_best_move,
        )

    # ------------------------------------------------------------------
    # Performance snapshots
    # ------------------------------------------------------------------

    async def save_snapshot(self, snapshot: Any) -> None:
        assert self._pool
        await self._pool.execute(
            """
            INSERT INTO performance_snapshots
                (username, period, rating, games_played, wins, losses, draws,
                 avg_acpl, puzzle_rating, puzzle_count, recorded_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            """,
            snapshot.username, snapshot.period, snapshot.rating,
            snapshot.games_played, snapshot.wins, snapshot.losses, snapshot.draws,
            snapshot.avg_acpl, snapshot.puzzle_rating, snapshot.puzzle_count,
            snapshot.recorded_at,
        )

    async def get_snapshot(self, username: str, period: str) -> Optional[dict[str, Any]]:
        assert self._pool
        row = await self._pool.fetchrow(
            "SELECT * FROM performance_snapshots WHERE username=$1 AND period=$2 ORDER BY recorded_at DESC LIMIT 1",
            username, period,
        )
        return dict(row) if row else None


def get_cache() -> RedisCache:
    return RedisCache(get_settings().redis_url)


def get_storage() -> PostgresStorage:
    return PostgresStorage(get_settings().database_url)
