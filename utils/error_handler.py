# -*- coding: utf-8 -*-
"""
utils/error_handler.py — Centralized error classification and user-friendly messages.

Provides:
- classify_ytdl_error()  — Detect copyright / unavailable / network / age-restricted
- playback_error_embed() — Beautiful red embed for playback failures
- handle_playback_error() — Send error notification to text channel
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
    UNKNOWN      = "unknown"


def classify_ytdl_error(exc: Exception) -> tuple[str, str, str]:
    """
    Classify a yt-dlp / playback exception.

    Returns a tuple of (error_type, title, description) — all user-facing strings.
    """
    msg = str(exc).lower()

    if any(k in msg for k in ("copyright", "removed", "blocked", "content warning")):
        return (
            YTDLErrorType.COPYRIGHT,
            "🚫 ติดลิขสิทธิ์ / Blocked",
            "เพลงนี้ถูกบล็อคหรือติดลิขสิทธิ์ในภูมิภาคนี้ ข้ามไปเพลงถัดไปให้นะครับ",
        )
    if any(k in msg for k in ("private video", "private", "members-only")):
        return (
            YTDLErrorType.PRIVATE,
            "🔒 วิดีโอไม่สาธารณะ",
            "วิดีโอนี้เป็น Private หรือเฉพาะสมาชิก ข้ามไปเพลงถัดไปให้นะครับ",
        )
    if any(k in msg for k in ("age", "sign in", "confirm your age")):
        return (
            YTDLErrorType.AGE_RESTRICT,
            "🔞 จำกัดอายุ",
            "วิดีโอนี้มีการจำกัดอายุ ไม่สามารถเล่นได้ ข้ามไปเพลงถัดไปให้นะครับ",
        )
    if any(k in msg for k in ("not available", "unavailable", "deleted", "does not exist")):
        return (
            YTDLErrorType.UNAVAILABLE,
            "❌ วิดีโอไม่พร้อมใช้งาน",
            "วิดีโอนี้ถูกลบหรือไม่พร้อมใช้งาน ข้ามไปเพลงถัดไปให้นะครับ",
        )
    if any(k in msg for k in ("429", "rate limit", "too many requests")):
        return (
            YTDLErrorType.RATE_LIMIT,
            "⏳ YouTube Rate Limit",
            "ดึงข้อมูลจาก YouTube ถี่เกินไป กรุณารอสักครู่แล้วลองใหม่นะครับ",
        )
    if any(k in msg for k in ("timeout", "connection", "network", "ssl", "errno")):
        return (
            YTDLErrorType.NETWORK,
            "🌐 ปัญหาเครือข่าย",
            "เชื่อมต่อไม่ได้ในขณะนี้ บอทจะข้ามไปเพลงถัดไปให้นะครับ",
        )

    return (
        YTDLErrorType.UNKNOWN,
        "⚠️ เกิดข้อผิดพลาด",
        "เล่นเพลงนี้ไม่ได้ บอทจะข้ามไปเพลงถัดไปให้นะครับ",
    )


# ── Error embeds ─────────────────────────────────────────────────────────────

def playback_error_embed(
    exc: Exception,
    track: Optional["Track"] = None,
    *,
    skipping: bool = True,
) -> discord.Embed:
    """
    Build a beautiful red embed describing a playback failure.
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
            name   = "🎵 เพลงที่มีปัญหา",
            value  = f"**{track.title[:80]}**",
            inline = False,
        )

    if skipping:
        e.add_field(
            name   = "⏭ สถานะ",
            value  = "กำลังข้ามไปเพลงถัดไปอัตโนมัติ...",
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
        title       = "⚠️ เกิดข้อผิดพลาด",
        description = "คำสั่งนี้ทำงานไม่สำเร็จ กรุณาลองใหม่อีกครั้งครับ",
        colour      = 0xED4245,
    )
    e.add_field(name="รายละเอียด", value=f"```{msg}```", inline=False)
    e.set_footer(text="ถ้าปัญหายังคงอยู่ โปรดแจ้งผู้ดูแลระบบ")
    return e


# ── Channel notifier ──────────────────────────────────────────────────────────

async def notify_playback_error(
    channel: discord.TextChannel,
    exc: Exception,
    track: Optional["Track"] = None,
    *,
    skipping: bool = True,
    delete_after: Optional[float] = 15.0,
) -> None:
    """
    Send a playback error embed to *channel*.
    Silently fails if the channel is unavailable.
    """
    try:
        embed = playback_error_embed(exc, track, skipping=skipping)
        await channel.send(embed=embed, delete_after=delete_after)
    except Exception as send_exc:
        logger.debug("Could not send error notification: %s", send_exc)
