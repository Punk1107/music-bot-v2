# -*- coding: utf-8 -*-
"""
core/audio_backend.py — Audio backend abstraction layer (P3-1: Lavalink Prep).

Defines an AudioBackend ABC that decouples the music cog from the concrete
audio implementation. This allows swapping FFmpeg for Lavalink (or any future
backend) with zero changes to the cog layer.

Available backends:
  FFmpegBackend   — Current default. Uses discord.FFmpegPCMAudio.
  LavalinkBackend — Stub. Requires wavelink + a running Lavalink Java server.

Configuration (in .env):
  AUDIO_BACKEND=ffmpeg   # "ffmpeg" (default) or "lavalink"

Usage in main.py setup_hook():
    from core.audio_backend import create_backend
    bot.audio_backend = create_backend()
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from core.audio import AudioEffectsProcessor
    from models.enums import AudioEffect

logger = logging.getLogger(__name__)


# ── Abstract Base ─────────────────────────────────────────────────────────────

class AudioBackend(ABC):
    """
    Abstract audio backend.

    All concrete backends must implement this contract so the music cog
    can call backend methods without knowing which implementation is active.
    """

    @abstractmethod
    async def play(
        self,
        vc:          discord.VoiceClient,
        stream_url:  str,
        after:       callable,
        *,
        ffmpeg_opts: dict,
    ) -> None:
        """
        Start playback on *vc* using *stream_url*.

        Args:
            vc:          The connected VoiceClient.
            stream_url:  Direct CDN audio URL (from yt-dlp / Lavalink).
            after:       Callback invoked when playback finishes (same
                         signature as discord.VoiceClient.play's after).
            ffmpeg_opts: Keyword options for FFmpegPCMAudio (ignored by
                         Lavalink backend but kept for interface parity).
        """
        ...

    @abstractmethod
    async def stop(self, vc: discord.VoiceClient) -> None:
        """Stop current playback on *vc*."""
        ...

    @abstractmethod
    async def set_volume(self, vc: discord.VoiceClient, volume: float) -> None:
        """
        Apply volume [0.0 – 2.0] to the active source.
        Implementations may silently ignore if source does not support it.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend name for logging."""
        ...


# ── FFmpeg Backend ────────────────────────────────────────────────────────────

class FFmpegBackend(AudioBackend):
    """
    Default backend — wraps discord.FFmpegPCMAudio.

    This is the existing implementation refactored behind the interface.
    Behaviour is identical to the pre-abstraction code.
    """

    @property
    def name(self) -> str:
        return "FFmpeg"

    async def play(
        self,
        vc:          discord.VoiceClient,
        stream_url:  str,
        after:       callable,
        *,
        ffmpeg_opts: dict,
    ) -> None:
        source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_opts)
        vc.play(source, after=after)
        logger.debug("FFmpegBackend: started playback via %s", stream_url[:60])

    async def stop(self, vc: discord.VoiceClient) -> None:
        if vc.is_playing() or vc.is_paused():
            vc.stop()

    async def set_volume(self, vc: discord.VoiceClient, volume: float) -> None:
        if vc.source and hasattr(vc.source, "volume"):
            try:
                vc.source.volume = volume
            except AttributeError:
                pass


# ── Lavalink Backend Stub ─────────────────────────────────────────────────────

class LavalinkBackend(AudioBackend):
    """
    Lavalink backend stub (P3-1 preparation).

    To activate this backend:
      1. Install wavelink:  pip install wavelink>=3.0
      2. Run a Lavalink server (Java): https://github.com/lavalink-devs/Lavalink
      3. Set AUDIO_BACKEND=lavalink in your .env
      4. Add LAVALINK_URI and LAVALINK_PASSWORD to your .env
      5. Replace the NotImplementedError bodies with wavelink calls.

    The interface is intentionally identical to FFmpegBackend so the cog
    layer requires zero modification when switching backends.
    """

    @property
    def name(self) -> str:
        return "Lavalink"

    async def play(
        self,
        vc:          discord.VoiceClient,
        stream_url:  str,
        after:       callable,
        *,
        ffmpeg_opts: dict,
    ) -> None:
        # TODO: Replace with wavelink.Player.play(track)
        raise NotImplementedError(
            "LavalinkBackend.play() requires wavelink + a running Lavalink server. "
            "See the docstring for setup instructions."
        )

    async def stop(self, vc: discord.VoiceClient) -> None:
        # TODO: Replace with wavelink.Player.stop()
        raise NotImplementedError("LavalinkBackend.stop() not yet implemented.")

    async def set_volume(self, vc: discord.VoiceClient, volume: float) -> None:
        # TODO: Replace with wavelink.Player.set_volume(int(volume * 100))
        raise NotImplementedError("LavalinkBackend.set_volume() not yet implemented.")


# ── Factory ───────────────────────────────────────────────────────────────────

def create_backend(backend_name: str = "ffmpeg") -> AudioBackend:
    """
    Instantiate and return the correct AudioBackend based on *backend_name*.

    Args:
        backend_name: "ffmpeg" (default) or "lavalink".
                      Read from config.AUDIO_BACKEND in production.

    Returns:
        An AudioBackend instance ready to use.
    """
    name = backend_name.lower().strip()
    if name == "lavalink":
        logger.info("Audio backend: LavalinkBackend (stub — requires wavelink)")
        return LavalinkBackend()
    else:
        if name != "ffmpeg":
            logger.warning(
                "Unknown AUDIO_BACKEND=%r — falling back to FFmpegBackend.", name
            )
        logger.info("Audio backend: FFmpegBackend")
        return FFmpegBackend()
