# -*- coding: utf-8 -*-
"""
utils/formatters.py — Text-formatting helpers for embeds and messages.
"""

from __future__ import annotations


def fmt_duration(seconds: int) -> str:
    """Return a human-readable duration string (HH:MM:SS or MM:SS)."""
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def progress_bar(
    elapsed: int,
    total: int,
    length: int = 20,
    filled: str = "▓",
    empty:  str = "░",
) -> str:
    """
    Build a Unicode progress bar.

    Example:  ▓▓▓▓▓▓▓░░░░░░░░░░░░░  1:23 / 3:45
    """
    if total <= 0:
        ratio = 0.0
    else:
        ratio = min(elapsed / total, 1.0)

    filled_len = round(ratio * length)
    bar = filled * filled_len + empty * (length - filled_len)
    return f"{bar}  {fmt_duration(elapsed)} / {fmt_duration(total)}"


def fmt_views(n: int | None) -> str:
    """Format a YouTube view count nicely, e.g. 1,234,567 → 1.23M."""
    if n is None:
        return "N/A"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def truncate(text: str, max_len: int = 60) -> str:
    return (text[:max_len - 1] + "…") if len(text) > max_len else text


def ordinal(n: int) -> str:
    """1 → '1st', 2 → '2nd', …"""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
