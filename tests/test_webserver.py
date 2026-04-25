import asyncio
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from webserver import handle_root, handle_health, handle_status, handle_ready

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.user.name = "TestBot"
    bot.user.avatar.url = "http://avatar.com"
    bot.latency = 0.05
    bot.guilds = [MagicMock(), MagicMock()]
    return bot

@pytest.mark.asyncio
async def test_health_check_handler():
    """Test health probe."""
    request = make_mocked_request("GET", "/health")
    response = await handle_health(request)
    assert response.status == 200

@pytest.mark.asyncio
async def test_dashboard_handler(mock_bot):
    """Test dashboard handler rendering."""
    app = web.Application()
    app["bot"] = mock_bot
    request = make_mocked_request("GET", "/", app=app)
    
    response = await handle_root(request)
    assert response.status == 200
    assert response.content_type == "text/html"
    
    # Assert dynamic injection
    html = response.text
    assert "2" in html  # Guild count
    assert "50" in html  # Latency
