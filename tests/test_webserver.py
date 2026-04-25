import pytest
from unittest.mock import AsyncMock, MagicMock
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from webserver import error_middleware, handle_root, handle_health, handle_status, handle_ready, get_bot_stats, BOT_KEY

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.start_time = None
    bot._players = {}
    bot.guilds = [1, 2, 3]
    bot.latency = 0.042
    bot.is_ready = MagicMock(return_value=True)
    return bot

@pytest.fixture
async def client(mock_bot):
    app = web.Application(middlewares=[error_middleware])
    app[BOT_KEY] = mock_bot

    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/status", handle_status)
    app.router.add_get("/ready", handle_ready)

    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()

@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data == {"status": "ok"}

@pytest.mark.asyncio
async def test_ready_endpoint(client, mock_bot):
    # Test when bot is ready
    resp = await client.get("/ready")
    assert resp.status == 200
    data = await resp.json()
    assert data == {"status": "ready"}

    # Test when bot is not ready
    mock_bot.is_ready.return_value = False
    resp2 = await client.get("/ready")
    assert resp2.status == 503
    data2 = await resp2.json()
    assert data2 == {"status": "starting"}

@pytest.mark.asyncio
async def test_status_endpoint(client):
    resp = await client.get("/status")
    assert resp.status == 200
    data = await resp.json()
    assert "uptime" in data
    assert data["guilds"] == 3
    assert data["latency"] == 42
    assert "players" in data
    assert "timestamp" in data

@pytest.mark.asyncio
async def test_root_endpoint(client):
    resp = await client.get("/")
    assert resp.status == 200
    assert resp.content_type == "text/html"
    text = await resp.text()
    assert "System Operational" in text
    assert "Music Bot V2 is running smoothly" in text

@pytest.mark.asyncio
async def test_error_middleware(client):
    # Simulate an error by patching the stats function
    import webserver
    original = webserver.get_bot_stats
    
    def raise_err(*args, **kwargs):
        raise ValueError("Simulated Error")
    
    webserver.get_bot_stats = raise_err
    try:
        resp = await client.get("/status")
        assert resp.status == 500
        data = await resp.json()
        assert data == {"error": "Internal Server Error"}
    finally:
        webserver.get_bot_stats = original
