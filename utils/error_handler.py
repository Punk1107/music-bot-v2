# -*- coding: utf-8 -*-
"""
utils/error_handler.py — Centralized error classification and user-friendly messages.

All user-facing strings are bilingual: English (primary) with Thai subtitle,
so the bot is accessible to both Thai-speaking communities and global users.

Provides:
- classify_ytdl_error()          — Detect copyright / unavailable / network / age-restricted
- playback_error_embed()         — Rich red embed for playback failures
- notify_playback_error()        — Send error notification to text channel
- command_error_embed()          — Slash-command error embed
- voice_connection_error_embed() — Voice reconnect failure embed [NEW]
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from models.track import Track

logger = logging.getLogger(__name__)


# ── Error classification ──────────────────────────────────────────────────────

class YTDLErrorType:
    COPYRIGHT    = "copyright"
    UNAVAILABLE  = "unavailable"
    AGE_RESTRICT = "age_restricted"
    PRIVATE      = "private"
    NETWORK      = "network"
    RATE_LIMIT   = "rate_limit"
    TIMEOUT      = "timeout"
    UNKNOWN      = "unknown"


def classify_ytdl_error(exc: Exception) -> tuple[str, str, str]:
    """
    Classify a yt-dlp / playback exception.

    Returns a tuple of (error_type, title, description) — all user-facing strings.
    Strings are bilingual: English primary, Thai secondary on a new line.
    """
    msg = str(exc).lower()

    if any(k in msg for k in ("copyright", "removed", "blocked", "content warning")):
        return (
            YTDLErrorType.COPYRIGHT,
            "🚫 Blocked — Copyright / Region Restricted",
            "This track is blocked or copyright-restricted in this region.\n"
            "*(เพลงนี้ถูกบล็อคหรือติดลิขสิทธิ์ในภูมิภาคนี้)*",
        )
    if any(k in msg for k in ("private video", "private", "members-only")):
        return (
            YTDLErrorType.PRIVATE,
            "🔒 Private / Members-Only Video",
            "This video is private or restricted to channel members.\n"
            "*(วิดีโอนี้เป็น Private หรือเฉพาะสมาชิก)*",
        )
    if any(k in msg for k in ("age", "sign in", "confirm your age")):
        return (
            YTDLErrorType.AGE_RESTRICT,
            "🔞 Age-Restricted Content",
            "This video requires age verification and cannot be played.\n"
            "*(วิดีโอนี้มีการจำกัดอายุ ไม่สามารถเล่นได้)*",
        )
    if any(k in msg for k in ("not available", "unavailable", "deleted", "does not exist")):
        return (
            YTDLErrorType.UNAVAILABLE,
            "❌ Video Unavailable",
            "This video has been deleted or is no longer available.\n"
            "*(วิดีโอนี้ถูกลบหรือไม่พร้อมใช้งาน)*",
        )
    if any(k in msg for k in ("429", "rate limit", "too many requests")):
        return (
            YTDLErrorType.RATE_LIMIT,
            "⏳ YouTube Rate Limited",
            "Too many requests to YouTube. Please wait a moment and try again.\n"
            "*(ดึงข้อมูลจาก YouTube ถี่เกินไป กรุณารอสักครู่)*",
        )
    # Separate timeout classification from generic network errors
    if "timeout" in msg or "timed out" in msg:
        return (
            YTDLErrorType.TIMEOUT,
            "⏱ Request Timed Out",
            "The audio source took too long to respond. The bot will skip to the next track.\n"
            "*(แหล่งเสียงตอบสนองช้าเกินไป บอทจะข้ามไปเพลงถัดไป)*",
        )
    if any(k in msg for k in ("connection", "network", "ssl", "errno")):
        return (
            YTDLErrorType.NETWORK,
            "🌐 Network Error",
            "Could not connect to the audio source. The bot will skip to the next track.\n"
            "*(เชื่อมต่อไม่ได้ในขณะนี้ บอทจะข้ามไปเพลงถัดไป)*",
        )

    return (
        YTDLErrorType.UNKNOWN,
        "⚠️ Playback Error",
        "An unexpected error occurred. The bot will skip to the next track.\n"
        "*(เกิดข้อผิดพลาดที่ไม่คาดคิด บอทจะข้ามไปเพลงถัดไป)*",
    )


# ── Error embeds ─────────────────────────────────────────────────────────────

def playback_error_embed(
    exc: Exception,
    track: Optional["Track"] = None,
    *,
    skipping: bool = True,
) -> discord.Embed:
    """
    Build a red embed describing a playback failure.
    If `skipping` is True, appends a note that the bot is auto-skipping.
    """
    error_type, title, description = classify_ytdl_error(exc)

    e = discord.Embed(
        title       = title,
        description = description,
        colour      = 0xED4245,  # Discord red
    )

    if track:
        e.add_field(
            name   = "🎵 Track",
            value  = f"**{track.title[:80]}**\n[Open link]({track.url})",
            inline = False,
        )

    if skipping:
        e.add_field(
            name   = "⏭ Action",
            value  = "Auto-skipping to the next track… *(กำลังข้ามไปเพลงถัดไปอัตโนมัติ)*",
            inline = False,
        )
    else:
        e.add_field(
            name   = "⏹ Action",
            value  = "Playback stopped — queue limit reached. *(หยุดการเล่นแล้ว)*",
            inline = False,
        )

    e.set_footer(text="Music Bot V2 • Error Handler")
    return e


def command_error_embed(error: Exception) -> discord.Embed:
    """Build a user-friendly embed for slash command errors."""
    msg = str(error)

    # Trim very long error messages
    if len(msg) > 200:
        msg = msg[:197] + "..."

    e = discord.Embed(
        title       = "⚠️ Command Failed",
        description = (
            "Something went wrong while running that command. Please try again.\n"
            "*(คำสั่งนี้ทำงานไม่สำเร็จ กรุณาลองใหม่อีกครั้ง)*"
        ),
        colour      = 0xED4245,
    )
    e.add_field(name="Details", value=f"```{msg}```", inline=False)
    e.set_footer(text="If this keeps happening, please contact a server administrator.")
    return e


def voice_connection_error_embed(
    channel_name: str = "voice channel",
    attempts: int = 3,
) -> discord.Embed:
    """
    Build an embed for a failed voice reconnect attempt.
    Sent to the text channel after all reconnect retries are exhausted.
    """
    e = discord.Embed(
        title       = "📡 Voice Reconnect Failed",
        description = (
            f"Failed to reconnect to **{channel_name}** after **{attempts}** attempt(s).\n"
            "Playback has been stopped. Please use `/play` to start a new session.\n\n"
            "*(บอทไม่สามารถเชื่อมต่อกลับได้ กรุณาพิมพ์ /play เพื่อเริ่มใหม่)*"
        ),
        colour      = 0xFEE75C,   # Warning yellow
    )
    e.set_footer(text="Music Bot V2 • Self-Healing System")
    return e


# ── Channel notifier ──────────────────────────────────────────────────────────

async def notify_playback_error(
    channel: discord.TextChannel,
    exc: Exception,
    track: Optional["Track"] = None,
    *,
    skipping: bool = True,
) -> None:
    """
    Send a playback error embed to *channel*.
    Messages persist permanently — no auto-delete.
    Silently fails if the channel is unavailable.
    """
    try:
        embed = playback_error_embed(exc, track, skipping=skipping)
        await channel.send(embed=embed)
    except Exception as send_exc:
        logger.debug("Could not send error notification: %s", send_exc)
