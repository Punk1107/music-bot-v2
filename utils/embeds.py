# -*- coding: utf-8 -*-
"""
utils/embeds.py — Discord embed factories.

All embed colours come from config so they stay consistent across the bot.
Changes in V2.1 refactor:
  - now_playing_embed uses COLOR_NOW_PLAYING (purple) for visual distinction
  - search/info embeds use COLOR_INFO (cyan)
  - Footer no longer hardcodes "Recently added"
  - loop field uses LoopMode.short_label() instead of brittle .replace() hack
  - track_added_embed accepts is_first=True to show "▶ Now Playing" title
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord

import config
from models.track import Track
from utils.formatters import fmt_duration, fmt_views, progress_bar, truncate


# ── Generic ───────────────────────────────────────────────────────────────────

def success_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"✅ {title}", description=description, colour=config.COLOR_SUCCESS)
    e.timestamp = datetime.now(timezone.utc)
    return e


def error_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"❌ {title}", description=description, colour=config.COLOR_ERROR)
    e.timestamp = datetime.now(timezone.utc)
    return e


def info_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"ℹ️ {title}", description=description, colour=config.COLOR_INFO)
    e.timestamp = datetime.now(timezone.utc)
    return e


def warning_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"⚠️ {title}", description=description, colour=config.COLOR_WARNING)
    e.timestamp = datetime.now(timezone.utc)
    return e


# ── Music-specific ────────────────────────────────────────────────────────────

def now_playing_embed(
    track: Track,
    *,
    elapsed:      int = 0,
    requester:    Optional[discord.Member] = None,
    loop_label:   str = "🔁 Loop Off",
    loop_short:   str = "Off",
    effects:      list[str] | None = None,
    volume:       float = 0.75,
    quality:      str = "MEDIUM",
    queue_count:  int = 0,
    queue_dur:    int = 0,
    channel_name: str = "",
) -> discord.Embed:
    bar = progress_bar(elapsed, track.duration)

    e = discord.Embed(
        title       = "🎵 Now Playing",
        description = f"**[{truncate(track.title, 80)}]({track.url})**",
        colour      = config.COLOR_NOW_PLAYING,
    )

    if track.thumbnail:
        e.set_thumbnail(url=track.thumbnail)

    # Row 1 — Duration | Requested by | Channel
    e.add_field(
        name="⏱ Duration",
        value=fmt_duration(track.duration),
        inline=True,
    )
    if requester:
        e.add_field(
            name="👤 Requested by",
            value=f"{requester.mention}",
            inline=True,
        )
    if channel_name:
        e.add_field(
            name="📺 Channel",
            value=channel_name,
            inline=True,
        )

    # Row 2 — Views | Queue | Loop
    e.add_field(
        name="👁 Views",
        value=fmt_views(track.view_count),
        inline=True,
    )
    queue_value = (
        f"{queue_count} track{'s' if queue_count != 1 else ''}"
        + (f" • {fmt_duration(queue_dur)}" if queue_dur else " • Live")
    )
    e.add_field(name="📋 Queue", value=queue_value, inline=True)
    # Use short_loop directly — no emoji stripping needed
    e.add_field(name="🔁 Loop", value=loop_short, inline=True)

    # Row 3 — Settings (Volume + Quality) spanning full width
    settings_value = f"Volume: {int(volume * 100)}% • Quality: {quality}"
    if effects:
        settings_value += f" • Effects: {', '.join(effects)}"
    e.add_field(name="⚙ Settings", value=settings_value, inline=False)

    # Progress bar
    e.add_field(
        name  = "🎶 Progress",
        value = f"`{bar}`",
        inline= False,
    )

    if requester:
        e.set_footer(
            text     = "Music Bot V2",
            icon_url = requester.display_avatar.url,
        )
    else:
        e.set_footer(text="Music Bot V2")

    e.timestamp = datetime.now(timezone.utc)
    return e


def queue_embed(
    tracks: list[Track],
    *,
    guild_name:       str = "",
    now_playing:      Optional[Track] = None,
    page:             int = 1,
    per_page:         int = 10,
    total_duration:   int = 0,
) -> discord.Embed:
    total_pages = max(1, -(-len(tracks) // per_page))  # ceiling division
    start = (page - 1) * per_page
    chunk = tracks[start: start + per_page]

    e = discord.Embed(
        title       = f"📋 Queue — {guild_name}",
        colour      = config.COLOR_PRIMARY,
        timestamp   = datetime.now(timezone.utc),
    )

    if now_playing:
        e.add_field(
            name  = "🎵 Now Playing",
            value = f"**{truncate(now_playing.title, 60)}** `{fmt_duration(now_playing.duration)}`",
            inline= False,
        )

    if not chunk:
        e.description = "_The queue is empty._"
    else:
        lines = []
        for i, t in enumerate(chunk, start=start + 1):
            lines.append(f"`{i}.` {truncate(t.title, 55)} `{fmt_duration(t.duration)}`")
        e.description = "\n".join(lines)

    e.set_footer(
        text=(
            f"Page {page}/{total_pages} · "
            f"{len(tracks)} track{'s' if len(tracks) != 1 else ''} · "
            f"Total: {fmt_duration(total_duration)}"
        )
    )
    return e


def search_results_embed(tracks: list[Track], query: str) -> discord.Embed:
    e = discord.Embed(
        title       = f"🔍 Search: {truncate(query, 50)}",
        description = "Select a track from the dropdown below.",
        colour      = config.COLOR_INFO,
        timestamp   = datetime.now(timezone.utc),
    )
    lines = []
    for i, t in enumerate(tracks[:10], 1):
        lines.append(
            f"`{i}.` **{truncate(t.title, 60)}**  ·  "
            f"`{fmt_duration(t.duration)}`  ·  {t.uploader}"
        )
    e.add_field(name="Results", value="\n".join(lines) or "_No results found._", inline=False)
    return e


def track_added_embed(
    track: Track,
    position: int,
    *,
    requester:    Optional[discord.Member] = None,
    channel_name: str = "",
    queue_count:  int = 0,
    queue_dur:    int = 0,
    is_first:     bool = False,   # True when this track starts playing immediately
) -> discord.Embed:
    # Dynamic title: distinguish "playing now" from "queued"
    title  = "▶ Now Playing" if is_first else "➕ Added to Queue"
    colour = config.COLOR_NOW_PLAYING if is_first else config.COLOR_SUCCESS

    e = discord.Embed(
        title       = title,
        description = f"**[{truncate(track.title, 70)}]({track.url})**",
        colour      = colour,
    )
    if track.thumbnail:
        e.set_thumbnail(url=track.thumbnail)

    # Row 1 — Duration | Requested by | Channel
    e.add_field(name="⏱ Duration", value=fmt_duration(track.duration), inline=True)
    if requester:
        e.add_field(name="👤 Requested by", value=requester.mention, inline=True)
    if channel_name:
        e.add_field(name="📺 Channel", value=channel_name, inline=True)

    # Row 2 — Views | Queue | Position
    e.add_field(name="👁 Views",    value=fmt_views(track.view_count), inline=True)
    queue_value = (
        f"{queue_count} track{'s' if queue_count != 1 else ''}"
        + (f" • {fmt_duration(queue_dur)}" if queue_dur else "")
    )
    e.add_field(name="📋 Queue",    value=queue_value, inline=True)
    pos_str = "▶ Up next" if is_first else f"#{position}"
    e.add_field(name="📌 Position", value=pos_str, inline=True)

    if requester:
        e.set_footer(
            text     = "Music Bot V2",
            icon_url = requester.display_avatar.url,
        )
    else:
        e.set_footer(text="Music Bot V2")

    e.timestamp = datetime.now(timezone.utc)
    return e


def history_embed(entries: list[dict], guild_name: str = "") -> discord.Embed:
    e = discord.Embed(
        title     = f"📜 Play History — {guild_name}",
        colour    = config.COLOR_INFO,
        timestamp = datetime.now(timezone.utc),
    )
    if not entries:
        e.description = "_No play history yet._"
        return e
    lines = []
    for item in entries:
        t    = item["track"]
        icon = "⏭" if item["skipped"] else "✅"
        lines.append(f"{icon} **{truncate(t.title, 55)}** `{fmt_duration(t.duration)}`")
    e.description = "\n".join(lines)
    return e


def help_embed() -> discord.Embed:
    e = discord.Embed(
        title       = "🎵 Music Bot V2 — Commands",
        description = "All commands use Discord slash commands (`/`)",
        colour      = config.COLOR_PRIMARY,
        timestamp   = datetime.now(timezone.utc),
    )

    e.add_field(
        name  = "🎶 Playback",
        value = (
            "`/join` · `/leave`\n"
            "`/play <query|URL>` · `/search <query>`\n"
            "`/pause` · `/resume` · `/skip` · `/stop`"
        ),
        inline=False,
    )
    e.add_field(
        name  = "📋 Queue",
        value = (
            "`/queue [page]` · `/shuffle` · `/clear`\n"
            "`/loop` · `/remove <position>` · `/move <from> <to>`"
        ),
        inline=False,
    )
    e.add_field(
        name  = "🎛 Audio",
        value = "`/volume <0-200>` · `/effects <effect>` · `/effects_clear` · `/effects_list`",
        inline=False,
    )
    e.add_field(
        name  = "📊 Info",
        value = "`/nowplaying` · `/history` · `/stats` · `/help`",
        inline=False,
    )
    e.set_footer(text="Music Bot V2 — Use /help for this menu at any time.")
    return e
