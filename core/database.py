# -*- coding: utf-8 -*-
"""
core/database.py — Async SQLite database manager using aiosqlite.

Handles:
- Schema initialisation & migrations
- Queue persistence (save / load per guild)
- Play history
- Server configuration storage
- User statistics
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import aiosqlite

import config
from models.track import Track
from models.server_config import ServerConfig

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous   = NORMAL;
PRAGMA foreign_keys  = ON;
PRAGMA cache_size    = 10000;
PRAGMA temp_store    = MEMORY;

CREATE TABLE IF NOT EXISTS queue (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    track_data TEXT    NOT NULL,
    position   INTEGER NOT NULL,
    added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    track_data      TEXT    NOT NULL,
    played_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_played INTEGER DEFAULT 0,
    skipped         BOOLEAN DEFAULT FALSE,
    completed       BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS server_configs (
    guild_id   INTEGER PRIMARY KEY,
    config_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_stats (
    user_id                 INTEGER NOT NULL,
    guild_id                INTEGER NOT NULL,
    total_tracks_requested  INTEGER DEFAULT 0,
    total_listening_time    INTEGER DEFAULT 0,
    favorite_tracks         TEXT    DEFAULT '[]',
    last_active             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, guild_id)
);

CREATE TABLE IF NOT EXISTS search_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    query      TEXT    NOT NULL,
    used_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_queue_guild_pos      ON queue(guild_id, position);
CREATE INDEX IF NOT EXISTS idx_history_guild_user   ON history(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_history_played_at    ON history(played_at);
CREATE INDEX IF NOT EXISTS idx_user_stats_guild     ON user_stats(guild_id);
CREATE INDEX IF NOT EXISTS idx_search_history_guild ON search_history(guild_id, used_at);
"""


class DatabaseManager:
    """Async SQLite database manager."""

    def __init__(self, db_path: str = config.DATABASE_PATH) -> None:
        self._db_path = db_path

    # ── Internals ─────────────────────────────────────────────────────────────

    @asynccontextmanager
    async def _connect(self):
        """Yield an open aiosqlite connection."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.executescript(
                "PRAGMA journal_mode=WAL;"
                "PRAGMA synchronous=NORMAL;"
                "PRAGMA foreign_keys=ON;"
                "PRAGMA cache_size=10000;"
                "PRAGMA temp_store=MEMORY;"
            )
            yield conn

    # ── Schema ────────────────────────────────────────────────────────────────

    async def initialise(self) -> None:
        """Create tables and indices if they do not exist."""
        async with self._connect() as conn:
            await conn.executescript(_SCHEMA_SQL)
            await conn.commit()
        logger.info("✅ Database initialised at %s", self._db_path)

    # ── Queue ─────────────────────────────────────────────────────────────────

    async def save_queue(
        self,
        guild_id: int,
        channel_id: int,
        tracks: list[Track],
    ) -> None:
        """Persist the current in-memory queue to SQLite."""
        async with self._connect() as conn:
            await conn.execute(
                "DELETE FROM queue WHERE guild_id = ?", (guild_id,)
            )
            rows = [
                (guild_id, channel_id, t.to_json(), pos, t.requester_id)
                for pos, t in enumerate(tracks)
            ]
            await conn.executemany(
                "INSERT INTO queue (guild_id, channel_id, track_data, position, user_id)"
                " VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            await conn.commit()

    async def load_queue(self, guild_id: int) -> list[Track]:
        """Load the persisted queue for a guild (sorted by position)."""
        async with self._connect() as conn:
            cursor = await conn.execute(
                "SELECT track_data FROM queue WHERE guild_id = ?"
                " ORDER BY position ASC",
                (guild_id,),
            )
            rows = await cursor.fetchall()
        tracks: list[Track] = []
        for row in rows:
            try:
                tracks.append(Track.from_json(row["track_data"]))
            except Exception as exc:
                logger.warning("Skipping corrupt queue row: %s", exc)
        return tracks

    async def clear_queue(self, guild_id: int) -> None:
        async with self._connect() as conn:
            await conn.execute(
                "DELETE FROM queue WHERE guild_id = ?", (guild_id,)
            )
            await conn.commit()

    # ── History ───────────────────────────────────────────────────────────────

    async def add_history(
        self,
        guild_id: int,
        user_id: int,
        track: Track,
        duration_played: int = 0,
        skipped: bool = False,
        completed: bool = False,
    ) -> None:
        async with self._connect() as conn:
            await conn.execute(
                "INSERT INTO history"
                " (guild_id, user_id, track_data, duration_played, skipped, completed)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    guild_id,
                    user_id,
                    track.to_json(),
                    duration_played,
                    skipped,
                    completed,
                ),
            )
            # Auto-purge old history
            await conn.execute(
                "DELETE FROM history WHERE guild_id = ?"
                " AND played_at < datetime('now', ? || ' days')",
                (guild_id, f"-{config.HISTORY_DAYS}"),
            )
            await conn.commit()

    async def get_history(
        self,
        guild_id: int,
        limit: int = 10,
    ) -> list[dict]:
        async with self._connect() as conn:
            cursor = await conn.execute(
                "SELECT track_data, played_at, skipped, completed"
                " FROM history WHERE guild_id = ?"
                " ORDER BY played_at DESC LIMIT ?",
                (guild_id, limit),
            )
            rows = await cursor.fetchall()
        results = []
        for row in rows:
            try:
                track = Track.from_json(row["track_data"])
                results.append(
                    {
                        "track":     track,
                        "played_at": row["played_at"],
                        "skipped":   bool(row["skipped"]),
                        "completed": bool(row["completed"]),
                    }
                )
            except Exception as exc:
                logger.warning("Skipping corrupt history row: %s", exc)
        return results

    # ── Server config ─────────────────────────────────────────────────────────

    async def get_server_config(self, guild_id: int) -> ServerConfig:
        async with self._connect() as conn:
            cursor = await conn.execute(
                "SELECT config_data FROM server_configs WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cursor.fetchone()
        if row:
            try:
                return ServerConfig.from_json(row["config_data"])
            except Exception as exc:
                logger.warning("Corrupt server config for guild %s: %s", guild_id, exc)
        return ServerConfig(guild_id=guild_id)

    async def save_server_config(self, cfg: ServerConfig) -> None:
        async with self._connect() as conn:
            await conn.execute(
                "INSERT INTO server_configs (guild_id, config_data, updated_at)"
                " VALUES (?, ?, CURRENT_TIMESTAMP)"
                " ON CONFLICT(guild_id) DO UPDATE SET"
                "   config_data = excluded.config_data,"
                "   updated_at  = CURRENT_TIMESTAMP",
                (cfg.guild_id, cfg.to_json()),
            )
            await conn.commit()

    # ── User stats ────────────────────────────────────────────────────────────

    async def increment_user_stats(
        self,
        guild_id: int,
        user_id: int,
        listening_seconds: int = 0,
    ) -> None:
        async with self._connect() as conn:
            await conn.execute(
                "INSERT INTO user_stats"
                "  (user_id, guild_id, total_tracks_requested, total_listening_time)"
                " VALUES (?, ?, 1, ?)"
                " ON CONFLICT(user_id, guild_id) DO UPDATE SET"
                "   total_tracks_requested = total_tracks_requested + 1,"
                "   total_listening_time   = total_listening_time + ?,"
                "   last_active            = CURRENT_TIMESTAMP",
                (user_id, guild_id, listening_seconds, listening_seconds),
            )
            await conn.commit()

    async def get_user_stats(
        self, guild_id: int, user_id: int
    ) -> Optional[dict]:
        async with self._connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM user_stats WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)

    # ── Search history (for autocomplete) ────────────────────────────────────

    async def save_search_query(
        self,
        guild_id: int,
        user_id: int,
        query: str,
    ) -> None:
        """
        Persist a search query for future autocomplete suggestions.
        Deduplicates by (guild_id, query) — updates used_at on conflict.
        Keeps at most 200 entries per guild.
        """
        query = query.strip()
        if not query or len(query) < 2:
            return
        async with self._connect() as conn:
            # Upsert: refresh timestamp if query already exists for this guild
            await conn.execute(
                "INSERT INTO search_history (guild_id, user_id, query)"
                " VALUES (?, ?, ?)"
                " ON CONFLICT DO NOTHING",
                (guild_id, user_id, query),
            )
            # Purge oldest entries beyond 200 per guild
            await conn.execute(
                "DELETE FROM search_history"
                " WHERE guild_id = ? AND id NOT IN ("
                "   SELECT id FROM search_history WHERE guild_id = ?"
                "   ORDER BY used_at DESC LIMIT 200"
                ")",
                (guild_id, guild_id),
            )
            await conn.commit()

    async def get_search_suggestions(
        self,
        guild_id: int,
        partial: str,
        limit: int = 25,
    ) -> list[str]:
        """
        Return up to *limit* search query suggestions for *guild_id* that
        start with (or contain) *partial*.  Ordered by recency.
        """
        partial = partial.strip()
        async with self._connect() as conn:
            if partial:
                cursor = await conn.execute(
                    "SELECT DISTINCT query FROM search_history"
                    " WHERE guild_id = ? AND query LIKE ?"
                    " ORDER BY used_at DESC LIMIT ?",
                    (guild_id, f"%{partial}%", limit),
                )
            else:
                cursor = await conn.execute(
                    "SELECT DISTINCT query FROM search_history"
                    " WHERE guild_id = ?"
                    " ORDER BY used_at DESC LIMIT ?",
                    (guild_id, limit),
                )
            rows = await cursor.fetchall()
        return [row["query"] for row in rows]
