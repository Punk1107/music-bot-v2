# -*- coding: utf-8 -*-
"""
webserver.py — Lightweight HTTP keep-alive server.

Starts a minimal Flask server on port 8080 in a background thread so
hosting platforms (Render, Railway, UptimeRobot) can ping the bot to
prevent it from sleeping.

Import this module only if Flask is available; the bot works without it.
"""

import logging
import threading

logger = logging.getLogger(__name__)


def start() -> None:
    """Start the keep-alive webserver in a daemon thread."""
    try:
        from flask import Flask
    except ImportError:
        logger.info("Flask not installed — keep-alive webserver disabled.")
        return

    app = Flask(__name__)

    @app.route("/")
    def index():
        return "🎵 Music Bot V2 is alive!", 200

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    def run():
        import os
        port = int(os.getenv("PORT", "8080"))
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    thread = threading.Thread(target=run, daemon=True, name="webserver")
    thread.start()
    logger.info("✅ Keep-alive webserver started on port 8080.")
