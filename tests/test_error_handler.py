from unittest.mock import AsyncMock, patch, MagicMock

import discord
import pytest

from utils.error_handler import (
    YTDLErrorType,
    classify_ytdl_error,
    command_error_embed,
    dev_error_embed,
    forward_to_dev_channel,
    notify_playback_error,
    playback_error_embed,
    voice_connection_error_embed,
)
from models.track import Track

def test_classify_ytdl_error():
    """Test classification of various exception strings."""
    # Copyright
    err, title, desc = classify_ytdl_error(Exception("This video contains content from UMG, who has blocked it on copyright grounds"))
    assert err == YTDLErrorType.COPYRIGHT
    assert "Copyright" in title

    # Private
    err, title, desc = classify_ytdl_error(Exception("Video is private"))
    assert err == YTDLErrorType.PRIVATE
    assert "Private" in title

    # Age restricted
    err, title, desc = classify_ytdl_error(Exception("Sign in to confirm your age"))
    assert err == YTDLErrorType.AGE_RESTRICT
    assert "Age" in title

    # Unavailable
    err, title, desc = classify_ytdl_error(Exception("Video unavailable"))
    assert err == YTDLErrorType.UNAVAILABLE
    assert "Unavailable" in title

    # Rate Limit
    err, title, desc = classify_ytdl_error(Exception("HTTP Error 429: Too Many Requests"))
    assert err == YTDLErrorType.RATE_LIMIT
    assert "Rate Limit" in title

    # Timeout
    err, title, desc = classify_ytdl_error(Exception("The read operation timed out"))
    assert err == YTDLErrorType.TIMEOUT
    assert "Timed Out" in title

    # Network
    err, title, desc = classify_ytdl_error(Exception("connection reset by peer"))
    assert err == YTDLErrorType.NETWORK
    assert "Network Error" in title

    # Unknown
    err, title, desc = classify_ytdl_error(Exception("Some weird error"))
    assert err == YTDLErrorType.UNKNOWN
    assert "Playback Error" in title

def test_playback_error_embed():
    """Test generating a playback error embed with and without a track."""
    track = Track("Test Title", "http://test", 100, "thumb", "Uploader")
    
    # With track, skipping=True
    embed = playback_error_embed(Exception("copyright blocked"), track, skipping=True)
    assert embed.title == "🚫 Blocked — Copyright / Region Restricted"
    assert "Test Title" in embed.fields[0].value
    assert "Auto-skipping" in embed.fields[1].value

    # Without track, skipping=False
    embed2 = playback_error_embed(Exception("connection reset"), None, skipping=False)
    assert embed2.title == "🌐 Network Error"
    assert len(embed2.fields) == 1
    assert "Playback stopped" in embed2.fields[0].value

def test_command_error_embed():
    """Test command error embed generation and message truncation."""
    long_msg = "a" * 300
    embed = command_error_embed(Exception(long_msg))
    assert embed.title == "⚠️ Command Failed"
    # Ensure truncation logic
    assert "..." in embed.fields[0].value
    assert len(embed.fields[0].value) < 250

def test_voice_connection_error_embed():
    """Test voice reconnect failure embed."""
    embed = voice_connection_error_embed("General Voice", 5)
    assert embed.title == "📡 Voice Reconnect Failed"
    assert "General Voice" in embed.description
    assert "5" in embed.description

def test_dev_error_embed():
    """Test dev error embed context building."""
    embed = dev_error_embed(
        Exception("Test"), 
        context="Testing", 
        guild_id=123, 
        user_id=456, 
        command="play"
    )
    assert "Exception: `Exception`" in embed.title
    assert "Testing" in embed.fields[0].value
    
    where_field = embed.fields[1].value
    assert "123" in where_field
    assert "456" in where_field
    assert "/play" in where_field

@pytest.mark.asyncio
@patch("config.DEV_LOG_CHANNEL_ID", 999)
async def test_forward_to_dev_channel():
    """Test dev channel forwarding logic."""
    
    bot = MagicMock()
    bot.fetch_channel = AsyncMock()
    channel = AsyncMock()
    bot.get_channel.return_value = channel
    
    await forward_to_dev_channel(bot, Exception("test"))
    bot.get_channel.assert_called_once_with(999)
    channel.send.assert_called_once()
    
    # Test fallback to fetch_channel
    bot.get_channel.return_value = None
    bot.fetch_channel.return_value = channel
    await forward_to_dev_channel(bot, Exception("test"))
    bot.fetch_channel.assert_called_once_with(999)

@pytest.mark.asyncio
async def test_notify_playback_error():
    """Test playback error notification to channel."""
    channel = AsyncMock()
    await notify_playback_error(channel, Exception("test"))
    channel.send.assert_called_once()
