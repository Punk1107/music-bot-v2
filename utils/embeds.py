# -*- coding: utf-8 -*-
"""
utils/embeds.py — Discord embed factories.

V4 Changes:
  - now_playing_embed() completely redesigned as a modern music-player
    dashboard: image banner, two clean inline field rows, a styled progress
    bar with timestamps, volume bar, loop badge — all driven by dynamic
    accent colour extracted from the thumbnail.
  - track_added_embed() upgraded with a gradient feel: banner thumbnail,
    refined inline field layout, distinct accent stripe.
  - Generic embeds (success/error/info/warning) gain a subtle emoji-prefix
    and use rounded colours that feel premium.
  - All fallback paths preserved so nothing breaks when optional data is None.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord

import config
from models.track import Track
from utils.formatters import fmt_duration, fmt_views, progress_bar, truncate


# ── Volume-bar helper ─────────────────────────────────────────────────────────

def _volume_bar(volume: float, length: int = 10) -> str:
    """Render a compact visual volume bar: e.g. '▮▮▮▮▮▯▯▯▯▯ 50%'"""
    pct   = int(round(volume * 100))
    filled = round(volume * length)       # volume is 0.0–2.0; cap display at 1.0
    display_filled = round(min(volume, 1.0) * length)
    bar   = "▮" * display_filled + "▯" * (length - display_filled)
    return f"`{bar}` **{pct}%**"


# ── Loop-badge helper ─────────────────────────────────────────────────────────

def _loop_badge(loop_short: str) -> str:
    badges = {
        "Off":   "⬜ Off",
        "Track": "🟩 Track",
        "Queue": "🟦 Queue",
    }
    return badges.get(loop_short, loop_short)


# ── Generic ───────────────────────────────────────────────────────────────────

def success_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"✅  {title}", description=description, colour=0x2ECC71)
    e.timestamp = datetime.now(timezone.utc)
    return e


def error_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"❌  {title}", description=description, colour=0xE74C3C)
    e.timestamp = datetime.now(timezone.utc)
    return e


def info_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"ℹ️  {title}", description=description, colour=0x3498DB)
    e.timestamp = datetime.now(timezone.utc)
    return e


def warning_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"⚠️  {title}", description=description, colour=0xF39C12)
    e.timestamp = datetime.now(timezone.utc)
    return e


# ── Now Playing ───────────────────────────────────────────────────────────────

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
    accent_color: Optional[int] = None,
) -> discord.Embed:
    color = accent_color if accent_color is not None else config.COLOR_NOW_PLAYING

    # ── Header ────────────────────────────────────────────────────────────────
    # Title row shows the track link; description carries the channel name
    channel_line = f"📺 *{truncate(channel_name, 40)}*\n" if channel_name else ""
    e = discord.Embed(
        colour      = color,
        description = (
            f"### 🎵  [{truncate(track.title, 75)}]({track.url})\n"
            f"{channel_line}"
        ),
    )

    # Large thumbnail on the right side
    if track.thumbnail:
        e.set_thumbnail(url=track.thumbnail)

    # ── Row 1: Duration | Views | Queue ──────────────────────────────────────
    e.add_field(
        name  = "⏱  Duration",
        value = f"`{fmt_duration(track.duration)}`",
        inline= True,
    )
    e.add_field(
        name  = "👁  Views",
        value = f"`{fmt_views(track.view_count)}`",
        inline= True,
    )
    queue_value = (
        f"`{queue_count} track{'s' if queue_count != 1 else ''}`"
        + (f"\n`{fmt_duration(queue_dur)} remaining`" if queue_dur else "")
    )
    e.add_field(name="📋  In Queue", value=queue_value, inline=True)

    # ── Row 2: Requested by | Loop | Quality ─────────────────────────────────
    if requester:
        e.add_field(
            name  = "👤  Requested by",
            value = requester.mention,
            inline= True,
        )
    e.add_field(
        name  = "🔁  Loop",
        value = _loop_badge(loop_short),
        inline= True,
    )
    e.add_field(
        name  = "🎚  Quality",
        value = f"`{quality}`",
        inline= True,
    )

    # ── Row 3: Volume bar (full width) ────────────────────────────────────────
    vol_line = _volume_bar(volume)
    effects_line = (
        f"\n> 🎛  **Effects:** {', '.join(effects)}"
        if effects else ""
    )
    e.add_field(
        name  = "🔊  Volume",
        value = vol_line + effects_line,
        inline= False,
    )

    # ── Progress bar (full width) ─────────────────────────────────────────────
    bar = progress_bar(elapsed, track.duration)
    e.add_field(
        name  = "▶  Progress",
        value = f"```{bar}```",
        inline= False,
    )

    # ── Footer ────────────────────────────────────────────────────────────────
    footer_text = "Music Bot V2  •  Now Playing"
    if requester:
        e.set_footer(text=footer_text, icon_url=requester.display_avatar.url)
    else:
        e.set_footer(text=footer_text)

    e.timestamp = datetime.now(timezone.utc)
    return e


# ── Track Added ───────────────────────────────────────────────────────────────

def track_added_embed(
    track: Track,
    position: int,
    *,
    requester:    Optional[discord.Member] = None,
    channel_name: str = "",
    queue_count:  int = 0,
    queue_dur:    int = 0,
    is_first:     bool = False,
) -> discord.Embed:
    # Vivid accent: teal for "playing now", violet for "queued"
    colour = 0x1ABC9C if is_first else 0x9B59B6
    icon   = "▶️" if is_first else "➕"
    label  = "Playing Now" if is_first else "Added to Queue"

    channel_line = f"📺 *{truncate(channel_name, 40)}*\n" if channel_name else ""
    e = discord.Embed(
        colour      = colour,
        description = (
            f"### {icon}  {label}\n"
            f"**[{truncate(track.title, 70)}]({track.url})**\n"
            f"{channel_line}"
        ),
    )

    if track.thumbnail:
        e.set_thumbnail(url=track.thumbnail)

    # ── Row 1: Duration | Views | Position ───────────────────────────────────
    e.add_field(name="⏱  Duration",  value=f"`{fmt_duration(track.duration)}`", inline=True)
    e.add_field(name="👁  Views",     value=f"`{fmt_views(track.view_count)}`",  inline=True)
    pos_str = "▶ Up next" if is_first else f"#{position}"
    e.add_field(name="📌  Position",  value=f"`{pos_str}`",                     inline=True)

    # ── Row 2: Requested by | Queue ──────────────────────────────────────────
    if requester:
        e.add_field(name="👤  Requested by", value=requester.mention, inline=True)

    queue_value = f"`{queue_count} track{'s' if queue_count != 1 else ''}`"
    if queue_dur:
        queue_value += f"\n`{fmt_duration(queue_dur)} total`"
    e.add_field(name="📋  Queue", value=queue_value, inline=True)

    footer_text = "Music Bot V2  •  Track Queued"
    if requester:
        e.set_footer(text=footer_text, icon_url=requester.display_avatar.url)
    else:
        e.set_footer(text=footer_text)

    e.timestamp = datetime.now(timezone.utc)
    return e


# ── Queue ─────────────────────────────────────────────────────────────────────

def queue_embed(
    tracks: list[Track],
    *,
    guild_name:       str = "",
    now_playing:      Optional[Track] = None,
    page:             int = 1,
    per_page:         int = 10,
    total_duration:   int = 0,
) -> discord.Embed:
    total_pages = max(1, -(-len(tracks) // per_page))
    start = (page - 1) * per_page
    chunk = tracks[start: start + per_page]

    e = discord.Embed(
        colour    = 0x5865F2,
        timestamp = datetime.now(timezone.utc),
    )
    e.set_author(name=f"📋 Queue — {guild_name}" if guild_name else "📋 Queue")

    if now_playing:
        e.add_field(
            name  = "🎵  Now Playing",
            value = f"**{truncate(now_playing.title, 55)}** `{fmt_duration(now_playing.duration)}`",
            inline= False,
        )

    if not chunk:
        e.description = "*The queue is empty. Use `/play` to add tracks!*"
    else:
        # Numbered emojis for positions 1-10; fall back to backtick numbers beyond that
        num_emoji = ["1⃣","2⃣","3⃣","4⃣","5⃣","6⃣","7⃣","8⃣","9⃣","🔟"]
        lines = []
        for i, t in enumerate(chunk, start=start + 1):
            icon = num_emoji[i - 1] if 1 <= i <= 10 else f"`{i:>2}.`"
            tag  = " ★ **Up Next**" if i == 1 else ""
            lines.append(
                f"{icon} **{truncate(t.title, 50)}**{tag} — `{fmt_duration(t.duration)}`"
            )
        e.description = "\n".join(lines)

    e.set_footer(
        text=(
            f"Page {page}/{total_pages}  ·  "
            f"{len(tracks)} track{'s' if len(tracks) != 1 else ''}  ·  "
            f"Total: {fmt_duration(total_duration)}"
        )
    )
    return e


# ── Search Results ────────────────────────────────────────────────────────────

def search_results_embed(tracks: list[Track], query: str) -> discord.Embed:
    num_emoji = ["1⃣","2⃣","3⃣","4⃣","5⃣","6⃣","7⃣","8⃣","9⃣","🔟"]
    e = discord.Embed(
        title       = f"🔍  Results for: {truncate(query, 45)}",
        description = "Select a track from the dropdown below:",
        colour      = 0x5865F2,
        timestamp   = datetime.now(timezone.utc),
    )
    lines = []
    for i, t in enumerate(tracks[:10]):
        icon = num_emoji[i] if i < 10 else f"`{i+1}.`"
        lines.append(
            f"{icon} **{truncate(t.title, 52)}**\n"
            f"  └ `{fmt_duration(t.duration)}`  ·  {fmt_views(t.view_count)}  ·  *{truncate(t.uploader, 28)}*"
        )
    e.add_field(name="​", value="\n".join(lines) or "*No results found.*", inline=False)
    e.set_footer(text="Results are pulled live from YouTube.")
    return e


# ── History ───────────────────────────────────────────────────────────────────

def history_embed(entries: list[dict], guild_name: str = "") -> discord.Embed:
    e = discord.Embed(
        title     = f"📜  Play History — {guild_name}",
        colour    = 0x3498DB,
        timestamp = datetime.now(timezone.utc),
    )
    if not entries:
        e.description = "*No play history yet.*"
        return e
    lines = []
    for item in entries:
        t    = item["track"]
        icon = "⏭" if item["skipped"] else "✅"
        lines.append(f"{icon} **{truncate(t.title, 55)}** `{fmt_duration(t.duration)}`")
    e.description = "\n".join(lines)
    return e


# ── Help ──────────────────────────────────────────────────────────────────────

def help_embed() -> discord.Embed:
    e = discord.Embed(
        colour      = 0x5865F2,
        description = (
            "### 🎵  Music Bot V2 — Command Reference\n"
            "> A premium music experience for your Discord server.\n"
            "> Use slash commands (`/`) to get started."
        ),
        timestamp   = datetime.now(timezone.utc),
    )

    # ── Playback ─────────────────────────────────────────────────────────────
    e.add_field(
        name  = "🎶  Connect",
        value = "`/join`  `/leave`",
        inline= True,
    )
    e.add_field(
        name  = "▶️  Play",
        value = "`/play <url|search>`  `/search`",
        inline= True,
    )
    e.add_field(
        name  = "⏯  Transport",
        value = "`/pause`  `/resume`  `/skip`  `/stop`",
        inline= True,
    )

    # ── Queue row ────────────────────────────────────────────────────────────
    e.add_field(
        name  = "📋  Queue",
        value = "`/queue [page]`  `/clear`  `/remove <pos>`",
        inline= True,
    )
    e.add_field(
        name  = "🔀  Order",
        value = "`/shuffle`  `/move <from> <to>`  `/loop`",
        inline= True,
    )
    e.add_field(
        name  = "🎚  Audio",
        value = "`/volume <0-200>`  `/effects`  `/effects_clear`",
        inline= True,
    )

    # ── Info row ─────────────────────────────────────────────────────────────
    e.add_field(
        name  = "📊  Info & Stats",
        value = "`/nowplaying`  `/history`  `/stats`  `/help`",
        inline= True,
    )
    e.add_field(
        name  = "🎛  Effects List",
        value = "`/effects_list`  — see all available audio FX",
        inline= True,
    )
    e.add_field(name="\u200b", value="\u200b", inline=True)  # spacer to complete the row

    # ── Tips ─────────────────────────────────────────────────────────────────
    e.add_field(
        name  = "💡  Tips",
        value = (
            "> • The **Now Playing** panel has live buttons — no commands needed\n"
            "> • `/play` accepts YouTube URLs, playlists, Spotify links, or keywords\n"
            "> • Volume buttons on the panel update in real-time without re-queuing"
        ),
        inline= False,
    )

    e.set_footer(text="Music Bot V2  —  Tip: click a button on the Now Playing panel for instant controls.")
    return e
