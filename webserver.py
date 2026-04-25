# -*- coding: utf-8 -*-
"""
webserver.py — Enterprise-grade Async Keep-Alive & Health Check Service

Replaces Flask with `aiohttp.web` to integrate natively with discord.py's
asyncio event loop. Provides zero-blocking endpoints for rendering status,
health probes, and a dashboard.
"""

import logging
import os
import time
from typing import TYPE_CHECKING, Any

import discord
from aiohttp import web

if TYPE_CHECKING:
    from discord.ext import commands

logger = logging.getLogger(__name__)

# Tiny in-memory cache to prevent excessive stat recalculations under heavy load
# Stores a tuple of (last_update_timestamp, stats_dict)
_STATS_CACHE: dict[str, Any] = {"time": 0.0, "data": {}}
CACHE_TTL = 15.0  # seconds

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Status - Music Bot V2</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f1115;
            --surface: #1e212b;
            --text: #e2e8f0;
            --text-muted: #94a3b8;
            --accent: #22d3ee;
            --success: #10b981;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg);
            color: var(--text);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background-image: 
                radial-gradient(circle at 15% 50%, rgba(88, 101, 242, 0.05), transparent 25%),
                radial-gradient(circle at 85% 30%, rgba(34, 211, 238, 0.05), transparent 25%);
        }
        .dashboard {
            background: var(--surface);
            padding: 2.5rem;
            border-radius: 20px;
            box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
            width: 100%;
            max-width: 500px;
            border: 1px solid rgba(255,255,255,0.05);
            animation: fadeIn 0.5s ease-out;
        }
        .header { text-align: center; margin-bottom: 2rem; }
        .header h1 { font-weight: 600; font-size: 1.8rem; margin-bottom: 0.5rem; }
        .header p { color: var(--text-muted); font-size: 0.95rem; }
        .status-dot {
            display: inline-block;
            width: 10px; height: 10px;
            background: var(--success);
            border-radius: 50%;
            margin-right: 8px;
            box-shadow: 0 0 10px var(--success);
            animation: pulse 2s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        .card {
            background: rgba(255,255,255,0.02);
            padding: 1.25rem;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.03);
            transition: transform 0.2s, background 0.2s;
        }
        .card:hover {
            transform: translateY(-2px);
            background: rgba(255,255,255,0.04);
            border-color: rgba(255,255,255,0.08);
        }
        .card-label { 
            color: var(--text-muted); 
            font-size: 0.85rem; 
            font-weight: 300; 
            text-transform: uppercase; 
            letter-spacing: 1px; 
            margin-bottom: 0.5rem; 
        }
        .card-value { font-size: 1.4rem; font-weight: 600; color: var(--accent); }
        .footer { 
            text-align: center; 
            margin-top: 2rem; 
            font-size: 0.8rem; 
            color: var(--text-muted); 
        }
        @keyframes pulse { 
            0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); } 
            70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); } 
            100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); } 
        }
        @keyframes fadeIn { 
            from { opacity: 0; transform: translateY(10px); } 
            to { opacity: 1; transform: translateY(0); } 
        }
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1><span class="status-dot"></span>System Operational</h1>
            <p>Music Bot V2 is running smoothly.</p>
        </div>
        <div class="grid">
            <div class="card">
                <div class="card-label">Uptime</div>
                <div class="card-value">{uptime}</div>
            </div>
            <div class="card">
                <div class="card-label">Latency</div>
                <div class="card-value">{latency}ms</div>
            </div>
            <div class="card">
                <div class="card-label">Guilds</div>
                <div class="card-value">{guilds}</div>
            </div>
            <div class="card">
                <div class="card-label">Active Players</div>
                <div class="card-value">{players}</div>
            </div>
        </div>
        <div class="footer">
            Enterprise Async Architecture • Last updated: {timestamp}
        </div>
    </div>
</body>
</html>"""


def format_uptime(seconds: float) -> str:
    """Format seconds into a human-readable uptime string."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d > 0:
        return f"{d}d {h}h {m}m"
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m {s}s"


def get_bot_stats(bot: "commands.Bot") -> dict[str, Any]:
    """Retrieve bot stats, using an in-memory cache to prevent blocking."""
    global _STATS_CACHE

    now = time.time()
    if now - _STATS_CACHE["time"] < CACHE_TTL and _STATS_CACHE["data"]:
        return _STATS_CACHE["data"]

    # Calculate Uptime
    start_time = getattr(bot, "start_time", None)
    uptime_str = "Unknown"
    if start_time:
        uptime_seconds = (discord.utils.utcnow() - start_time).total_seconds()
        uptime_str = format_uptime(uptime_seconds)

    # Calculate Active Players
    active_players = 0
    if hasattr(bot, "_players"):
        active_players = sum(
            1 for p in bot._players.values() if p.now_playing is not None
        )

    stats = {
        "uptime": uptime_str,
        "guilds": len(bot.guilds),
        "latency": round(bot.latency * 1000) if bot.latency else 0,
        "players": active_players,
        "timestamp": discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    _STATS_CACHE["time"] = now
    _STATS_CACHE["data"] = stats

    return stats


@web.middleware
async def error_middleware(request: web.Request, handler) -> web.Response:
    """Basic middleware to catch errors and prevent webserver crash."""
    try:
        return await handler(request)
    except web.HTTPException as ex:
        # Allow standard HTTP exceptions to pass through
        raise ex
    except Exception as ex:
        logger.error(
            "Webserver caught unhandled exception processing %s %s: %s",
            request.method,
            request.path,
            ex,
            exc_info=True,
        )
        return web.json_response(
            {"error": "Internal Server Error"}, status=500
        )


async def handle_root(request: web.Request) -> web.Response:
    """Render the stylish HTML dashboard."""
    bot = request.app["bot"]
    stats = get_bot_stats(bot)

    html = HTML_TEMPLATE.format(
        uptime=stats["uptime"],
        latency=stats["latency"],
        guilds=stats["guilds"],
        players=stats["players"],
        timestamp=stats["timestamp"],
    )
    return web.Response(text=html, content_type="text/html")


async def handle_health(request: web.Request) -> web.Response:
    """Simple health probe for Docker / keep-alive systems."""
    return web.json_response({"status": "ok"})


async def handle_status(request: web.Request) -> web.Response:
    """Detailed JSON payload of bot metrics."""
    bot = request.app["bot"]
    stats = get_bot_stats(bot)
    return web.json_response(stats)


async def handle_ready(request: web.Request) -> web.Response:
    """Readiness probe. Returns 200 if connected to gateway, else 503."""
    bot = request.app["bot"]
    if bot.is_ready():
        return web.json_response({"status": "ready"}, status=200)
    return web.json_response({"status": "starting"}, status=503)


async def start_webserver(bot: "commands.Bot") -> web.AppRunner:
    """
    Start the aiohttp web server using the bot's event loop.
    Returns the AppRunner to allow graceful shutdown later.
    """
    app = web.Application(middlewares=[error_middleware])
    app["bot"] = bot

    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/status", handle_status)
    app.router.add_get("/ready", handle_ready)

    runner = web.AppRunner(app, access_log=None) # Disable noisy access logs to save CPU
    await runner.setup()

    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("✅ Async Enterprise Webserver started natively on port %d.", port)
    return runner
