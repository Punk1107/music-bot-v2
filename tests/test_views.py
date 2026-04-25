import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from utils.views import MusicControlView, QueueView, SearchSelectView
from models.track import Track
from models.enums import LoopMode

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.get_guild = MagicMock()
    return bot

@pytest.fixture
def mock_player():
    player = MagicMock()
    player.__len__.return_value = 5
    player.now_playing = Track("Title", "http://url", 100, "thumb", "Uploader")
    player.volume = 1.0
    player.loop_mode = LoopMode.OFF
    player.shuffle = AsyncMock()
    player.as_list.return_value = [
        Track(f"Title {i}", "http://url", 100, "thumb", "Uploader") for i in range(15)
    ]
    player.queue_duration.return_value = 1500
    player.elapsed_seconds.return_value = 10
    player.accent_color = None
    player.effects = []
    player.quality = "high"
    return player

@pytest.fixture
def mock_interaction():
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.voice = MagicMock()
    interaction.user.voice.channel = MagicMock()
    
    # Mock data for select
    interaction.data = {"values": ["2"]}
    return interaction

@pytest.mark.asyncio
async def test_music_control_sync_buttons(mock_bot, mock_player):
    """Test MusicControlView button sync logic. Covers lines 63-97"""
    mock_bot.get_player.return_value = mock_player
    
    view = MusicControlView(bot=mock_bot, guild_id=123)
    view._sync_buttons()
    
    for child in view.children:
        if getattr(child, "custom_id", None) == "mb_skip":
            assert child.label == "⏭ Skip (5)"
            assert not child.disabled
        elif getattr(child, "custom_id", None) == "mb_shuffle":
            assert not child.disabled
        elif getattr(child, "custom_id", None) == "mb_loop":
            assert child.label == "🔁 Loop Off"
            
    # Test empty queue state
    mock_player.__len__.return_value = 0
    mock_player.now_playing = None
    view._sync_buttons()
    
    for child in view.children:
        if getattr(child, "custom_id", None) == "mb_skip":
            assert child.label == "⏭ Skip"
            assert child.disabled
        elif getattr(child, "custom_id", None) == "mb_shuffle":
            assert child.disabled

@pytest.mark.asyncio
async def test_music_control_check(mock_bot, mock_player, mock_interaction):
    """Test MusicControlView voice channel check. Covers lines 101-123"""
    mock_guild = MagicMock()
    mock_vc = MagicMock()
    mock_guild.voice_client = mock_vc
    mock_bot.get_guild.return_value = mock_guild
    mock_bot.get_player.return_value = mock_player
    view = MusicControlView(bot=mock_bot, guild_id=123)
    
    # Matching voice channels
    mock_interaction.user.voice.channel = mock_vc.channel
    assert await view._check(mock_interaction) is True
    
    # Mismatching voice channels
    mock_interaction.user.voice.channel = MagicMock()
    assert await view._check(mock_interaction) is False

@pytest.mark.asyncio
async def test_music_control_shuffle(mock_bot, mock_player, mock_interaction):
    """Test shuffle button callback. Covers lines 213-246"""
    mock_bot.get_player.return_value = mock_player
    mock_guild = MagicMock()
    mock_guild.voice_client = MagicMock()
    mock_interaction.user.voice.channel = mock_guild.voice_client.channel
    mock_bot.get_guild.return_value = mock_guild
    
    view = MusicControlView(bot=mock_bot, guild_id=123)
    button = [c for c in view.children if getattr(c, "custom_id", None) == "mb_shuffle"][0]
    
    await button.callback(mock_interaction)
    
    mock_player.shuffle.assert_called_once()
    mock_interaction.response.edit_message.assert_called_once()
    
    # Assert embed modification
    args, kwargs = mock_interaction.response.edit_message.call_args
    embed = kwargs.get("embed")
    assert embed is not None
    assert "🔀 **Queue shuffled!**" in embed.description

@pytest.mark.asyncio
async def test_music_control_volume(mock_bot, mock_player, mock_interaction):
    """Test volume button callbacks. Covers lines 300-334"""
    mock_bot.get_player.return_value = mock_player
    mock_guild = MagicMock()
    mock_vc = MagicMock()
    mock_vc.source = MagicMock()
    mock_guild.voice_client = mock_vc
    mock_interaction.user.voice.channel = mock_vc.channel
    mock_bot.get_guild.return_value = mock_guild
    
    view = MusicControlView(bot=mock_bot, guild_id=123)
    
    vol_down_btn = [c for c in view.children if getattr(c, "custom_id", None) == "mb_vol_down"][0]
    vol_up_btn = [c for c in view.children if getattr(c, "custom_id", None) == "mb_vol_up"][0]
    
    # Test Volume Down
    mock_player.volume = 1.0
    await vol_down_btn.callback(mock_interaction)
    assert round(mock_player.volume, 1) == 0.9
    
    # Test Volume Up
    mock_player.volume = 1.0
    await vol_up_btn.callback(mock_interaction)
    assert round(mock_player.volume, 1) == 1.1

@pytest.mark.asyncio
async def test_queue_view_rebuild_select(mock_bot, mock_player):
    """Test QueueView dynamic select rebuilding. Covers lines 518-559"""
    mock_bot.get_player.return_value = mock_player
    
    # Queue size is 15 tracks
    view = QueueView(bot=mock_bot, guild_id=123)
    view.page = 1
    view._rebuild_select()
    
    select = [c for c in view.children if getattr(c, "custom_id", None) == "queue_track_select"]
    assert len(select) == 1
    assert len(select[0].options) == 10 # 10 items per page
    
    # Page 2 should have 5 tracks
    view.page = 2
    view._rebuild_select()
    select = [c for c in view.children if getattr(c, "custom_id", None) == "queue_track_select"]
    assert len(select[0].options) == 5

@pytest.mark.asyncio
async def test_music_control_stop(mock_bot, mock_player, mock_interaction):
    """Test MusicControlView stop button callback. Covers lines 257-287"""
    mock_bot.get_player.return_value = mock_player
    mock_guild = MagicMock()
    mock_vc = MagicMock()
    mock_vc.disconnect = AsyncMock()
    mock_guild.voice_client = mock_vc
    mock_interaction.user.voice.channel = mock_vc.channel
    mock_bot.get_guild.return_value = mock_guild
    
    view = MusicControlView(bot=mock_bot, guild_id=123)
    stop_btn = [c for c in view.children if getattr(c, "custom_id", None) == "mb_stop"][0]
    
    await stop_btn.callback(mock_interaction)
    
    mock_player.reset.assert_called_once()
    mock_vc.stop.assert_called_once()
    mock_vc.disconnect.assert_called_once()
    mock_interaction.response.edit_message.assert_called_once()

@pytest.mark.asyncio
async def test_search_select_view(mock_interaction):
    """Test SearchSelectView on_select callback. Covers lines 397-431"""
    tracks = [Track(f"T{i}", "http://url", 100, "thumb", "Up") for i in range(15)]
    mock_callback = AsyncMock()
    
    view = SearchSelectView(tracks=tracks, callback=mock_callback)
    
    # Assert options truncated correctly
    select = view.children[0]
    assert len(select.options) == 10
    
    # Fire on_select
    await select.callback(mock_interaction)
    
    mock_interaction.response.defer.assert_called_once()
    mock_callback.assert_called_once_with(2)  # value is "2"

    # Test Exception flow
    mock_callback.side_effect = Exception("Test Fail")
    view2 = SearchSelectView(tracks=tracks, callback=mock_callback)
    select2 = view2.children[0]
    await select2.callback(mock_interaction)
    mock_interaction.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_queue_view_on_track_select(mock_bot, mock_player, mock_interaction):
    """Test QueueView dynamic action buttons injection. Covers lines 563-604"""
    mock_bot.get_player.return_value = mock_player
    view = QueueView(bot=mock_bot, guild_id=123)
    
    # Manually trigger select callback
    await view._on_track_select(mock_interaction)
    
    # Check that remove/top/cancel buttons were injected
    action_buttons = [c for c in view.children if getattr(c, "custom_id", None) in {"queue_action_remove", "queue_action_top", "queue_action_cancel"}]
    assert len(action_buttons) == 3
    
    mock_interaction.response.edit_message.assert_called_once()

@pytest.mark.asyncio
@patch("asyncio.sleep", AsyncMock())
async def test_queue_view_on_action_remove(mock_bot, mock_player, mock_interaction):
    """Test queue view removal. Covers _on_action_remove logic"""
    mock_bot.get_player.return_value = mock_player
    view = QueueView(bot=mock_bot, guild_id=123)
    
    # Test with no selected idx
    view._selected_idx = None
    await view._on_action_remove(mock_interaction)
    mock_interaction.response.defer.assert_called_once()
    
    # Test with selected idx
    mock_interaction.reset_mock()
    view._selected_idx = 2
    
    # Setup player.remove to return a mock track
    mock_removed_track = Track("Removed Title", "http://url", 100, "thumb", "Uploader")
    mock_player.remove = AsyncMock(return_value=mock_removed_track)
    
    await view._on_action_remove(mock_interaction)
    
    mock_player.remove.assert_called_once_with(2)
    assert view._selected_idx is None
    mock_interaction.response.edit_message.assert_called_once()
    mock_interaction.edit_original_response.assert_called_once()
    
    # Test failed removal (returns None)
    mock_interaction.reset_mock()
    view._selected_idx = 2
    mock_player.remove = AsyncMock(return_value=None)
    
    await view._on_action_remove(mock_interaction)
    mock_interaction.response.edit_message.assert_called_once()
    
    args, kwargs = mock_interaction.response.edit_message.call_args
    assert "no longer in the queue" in kwargs["embed"].description
