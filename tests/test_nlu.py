import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from core.nlu import NLUPipeline, NLUResult

@pytest.fixture
def mock_openai_response():
    return {
        "choices": [
            {
                "message": {
                    "content": '{"action": "play", "params": {"query": "lofi hip hop"}}'
                }
            }
        ]
    }

@pytest.fixture
def mock_anthropic_response():
    return {
        "content": [
            {
                "text": '{"action": "skip", "params": {}}'
            }
        ]
    }

@pytest.mark.asyncio
@patch("os.getenv")
async def test_nlu_openai_parse(mock_getenv, mock_openai_response):
    """Test OpenAI parsing flow."""
    # Setup environment mocks
    def getenv_side_effect(key, default=None):
        if key == "NLU_ENABLED": return "true"
        if key == "NLU_PROVIDER": return "openai"
        if key == "OPENAI_API_KEY": return "test-openai-key"
        if key == "NLU_MAX_TOKENS": return "256"
        return default
    mock_getenv.side_effect = getenv_side_effect
    
    pipeline = NLUPipeline()
    assert pipeline.enabled is True
    
    # Mock aiohttp session
    mock_session = MagicMock()
    mock_session.closed = False
    mock_post = AsyncMock()
    mock_response = AsyncMock()
    mock_response.json.return_value = mock_openai_response
    mock_response.raise_for_status = AsyncMock()
    mock_post.__aenter__.return_value = mock_response
    mock_session.post.return_value = mock_post

    result = await pipeline.parse("play some lofi", session=mock_session)
    
    assert isinstance(result, NLUResult)
    assert result.action == "play"
    assert result.params["query"] == "lofi hip hop"
    assert bool(result) is True


@pytest.mark.asyncio
@patch("os.getenv")
async def test_nlu_anthropic_parse(mock_getenv, mock_anthropic_response):
    """Test Anthropic parsing flow."""
    # Setup environment mocks
    def getenv_side_effect(key, default=None):
        if key == "NLU_ENABLED": return "true"
        if key == "NLU_PROVIDER": return "anthropic"
        if key == "ANTHROPIC_API_KEY": return "test-anthropic-key"
        if key == "NLU_MAX_TOKENS": return "256"
        return default
    mock_getenv.side_effect = getenv_side_effect
    
    pipeline = NLUPipeline()
    assert pipeline.enabled is True
    
    # Mock aiohttp session
    mock_session = MagicMock()
    mock_session.closed = False
    mock_post = AsyncMock()
    mock_response = AsyncMock()
    mock_response.json.return_value = mock_anthropic_response
    mock_response.raise_for_status = AsyncMock()
    mock_post.__aenter__.return_value = mock_response
    mock_session.post.return_value = mock_post

    result = await pipeline.parse("skip this track", session=mock_session)
    
    assert isinstance(result, NLUResult)
    assert result.action == "skip"
    assert result.params == {}

@pytest.mark.asyncio
@patch("os.getenv")
async def test_nlu_parse_errors(mock_getenv):
    """Test NLU parse errors (disabled, empty, JSON errors)."""
    # Test disabled
    def disabled_getenv(key, default=None):
        if key == "NLU_ENABLED": return "false"
        if key == "NLU_MAX_TOKENS": return "256"
        return default
    mock_getenv.side_effect = disabled_getenv
    pipeline = NLUPipeline()
    assert await pipeline.parse("play") is None

    # Enable and test malformed JSON
    def getenv_side_effect(key, default=None):
        if key == "NLU_ENABLED": return "true"
        if key == "NLU_PROVIDER": return "openai"
        if key == "OPENAI_API_KEY": return "test-openai-key"
        if key == "NLU_MAX_TOKENS": return "256"
        return default
    mock_getenv.side_effect = getenv_side_effect

    pipeline = NLUPipeline()
    
    # Empty string
    assert await pipeline.parse("") is None

    # Test malformed response using internal helper
    res = pipeline._parse_response("not json")
    assert res.action == "unknown"
    assert res.params["raw"] == "not json"
    assert bool(res) is False
