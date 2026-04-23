# -*- coding: utf-8 -*-
"""models/server_config.py — Per-guild bot configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass

import config


@dataclass
class ServerConfig:
    guild_id:                 int
    max_queue_size:           int   = config.MAX_QUEUE_SIZE
    max_user_queue:           int   = config.MAX_USER_QUEUE
    max_track_length:         int   = config.MAX_TRACK_LENGTH
    volume:                   float = 0.75
    auto_disconnect_timeout:  int   = config.IDLE_TIMEOUT
    duplicate_protection:     bool  = True
    effects_enabled:          bool  = True
    announce_songs:           bool  = True
    show_progress:            bool  = True
    quality:                  str   = "MEDIUM"

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "guild_id":                self.guild_id,
            "max_queue_size":          self.max_queue_size,
            "max_user_queue":          self.max_user_queue,
            "max_track_length":        self.max_track_length,
            "volume":                  self.volume,
            "auto_disconnect_timeout": self.auto_disconnect_timeout,
            "duplicate_protection":    self.duplicate_protection,
            "effects_enabled":         self.effects_enabled,
            "announce_songs":          self.announce_songs,
            "show_progress":           self.show_progress,
            "quality":                 self.quality,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "ServerConfig":
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    @classmethod
    def from_json(cls, raw: str) -> "ServerConfig":
        return cls.from_dict(json.loads(raw))
