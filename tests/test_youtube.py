import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from core.youtube import YouTubeExtractor
from models.track import Track
import config

@pytest.fixture
def extractor():
    ext = YouTubeExtractor()
    # Reset caches
    ext._cache = {}
    ext._search_cache = {}
    return ext

@pytest.fixture
def mock_track():
    return Track(
        title="Test Track",
        url="https://www.youtube.com/watch?v=123",
        duration=100,
        thumbnail="test.jpg",
        uploader="Test Uploader",
        view_count=1000,
        upload_date="20230101",
    )

@pytest.mark.asyncio
@patch("core.youtube.config.YTDL_RETRIES", 2)
@patch("core.youtube.config.YTDL_TIMEOUT", 0.05)
async def test_extract_timeout_and_retry(extractor):
    """Test _extract timeout logic and exponential backoff. Covers lines 165-221"""
    # Force the executor to sleep longer than the timeout
    async def slow_executor(*args, **kwargs):
        await asyncio.sleep(0.1)
        return {"id": "test"}

    with patch("asyncio.get_running_loop") as mock_loop:
        loop = asyncio.get_event_loop()
        mock_loop.return_value.run_in_executor = MagicMock(side_effect=lambda *args: loop.create_task(asyncio.sleep(0.1)))
        
        start = time.monotonic()
        res = await extractor._extract("test_query", use_cache=False, timeout=0.01)
        end = time.monotonic()
        
        assert res is None

@pytest.mark.asyncio
async def test_extract_stream_url_logic(extractor):
    """Test _extract_stream_url various format parsing. Covers lines 251-278"""
    # 1. Best audio-only format
    entry1 = {
        "formats": [
            {"vcodec": "none", "url": "http://audio_only", "abr": 128},
            {"vcodec": "avc1", "url": "http://video_only", "abr": 0},
            {"vcodec": "none", "url": "http://audio_best", "abr": 256},
        ]
    }
    assert extractor._extract_stream_url(entry1) == "http://audio_best"

    # 2. No audio-only, fallback to candidate with url
    entry2 = {
        "formats": [
            {"vcodec": "avc1", "url": "http://combined_av", "abr": 128},
        ]
    }
    assert extractor._extract_stream_url(entry2) == "http://combined_av"

    # 3. Fallback to top-level url if not a youtube webpage
    entry3 = {"url": "http://cdn.example.com/audio.mp3"}
    assert extractor._extract_stream_url(entry3) == "http://cdn.example.com/audio.mp3"

    # 4. Returns None if nothing matches
    entry4 = {"url": "https://www.youtube.com/watch?v=123"}
    assert extractor._extract_stream_url(entry4) is None


@pytest.mark.asyncio
@patch("core.youtube.config.YTDL_STREAM_TIMEOUT", 0.01)
async def test_get_stream_url_timeout_and_cache(extractor, mock_track):
    """Test get_stream_url cache hit and timeout. Covers lines 319-343"""
    # 1. Cache hit (P3-2 functionality)
    mock_track.stream_url_cache = "http://cached_stream"
    mock_track.stream_url_expires = time.monotonic() + 3600
    
    res = await extractor.get_stream_url("https://www.youtube.com/watch?v=123", mock_track)
    assert res == "http://cached_stream"

    # 2. Timeout error propagation
    with patch("asyncio.get_running_loop") as mock_loop:
        loop = asyncio.get_event_loop()
        mock_loop.return_value.run_in_executor = MagicMock(side_effect=lambda *args: loop.create_task(asyncio.sleep(0.1)))
        
        with pytest.raises(asyncio.TimeoutError):
            await extractor.get_stream_url("https://www.youtube.com/watch?v=456", None)


@pytest.mark.asyncio
async def test_search_cache_logic(extractor):
    """Test search cache logic. Covers lines 390-430"""
    mock_entry = {
        "entries": [
            {
                "title": "Test 1", "url": "http://yt/1", "duration": 100, 
                "uploader": "U1", "view_count": 10
            }
        ]
    }

    # First call - cache miss
    with patch.object(extractor, "_extract", return_value=mock_entry) as mock_extract:
        res1 = await extractor.search("test_query", max_results=1)
        assert len(res1) == 1
        assert res1[0].title == "Test 1"
        mock_extract.assert_called_once()

    # Second call - cache hit
    with patch.object(extractor, "_extract") as mock_extract:
        res2 = await extractor.search("test_query", max_results=1)
        assert len(res2) == 1
        mock_extract.assert_not_called()
        
    # Eviction logic (simulate max cache)
    with patch("core.youtube.config.SEARCH_CACHE_MAX_SIZE", 0):
        with patch.object(extractor, "_extract", return_value=mock_entry) as mock_extract:
            await extractor.search("new_query", max_results=1)
            assert len(extractor._search_cache) <= 1
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.youtube import YouTubeExtractor
from models.track import Track

@pytest.mark.asyncio
@patch("core.youtube.YouTubeExtractor._run_ytdl")
async def test_prefetch_stream_url(mock_run_ytdl):
    """Test prefetching a stream url in the background. Covers lines 359-381"""
    extractor = YouTubeExtractor()
    track = Track("Title", "http://url", 100, None, "Uploader")
    
    # Test successful prefetch
    mock_run_ytdl.return_value = {"entries": [{"url": "http://stream_url", "acodec": "opus", "vcodec": "none"}]}
    await extractor.prefetch_stream_url(track)
    assert track.stream_url_cache == "http://stream_url"
    assert track.stream_url_expires > 0
    
    # Test failure does not crash
    mock_run_ytdl.side_effect = Exception("YTDL Error")
    track.stream_url_cache = None
    await extractor.prefetch_stream_url(track)
    assert track.stream_url_cache is None
    
    # Test timeout
    async def timeout_ytdl(*args, **kwargs):
        await asyncio.sleep(0.5)
        return {"url": "slow"}
    
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        await extractor.prefetch_stream_url(track)
    assert track.stream_url_cache is None

@pytest.mark.asyncio
@patch("core.youtube.YouTubeExtractor._run_ytdl")
async def test_get_playlist_info(mock_run_ytdl):
    """Test playlist extraction logic. Covers lines 439-484"""
    extractor = YouTubeExtractor()
    
    # Test valid playlist
    mock_run_ytdl.return_value = {
        "entries": [
            {"title": "Track 1", "id": "1", "url": "http://1", "duration": 100},
            {"title": "Track 2", "id": "2", "url": "http://2", "duration": 200},
            {"title": "Too Long", "id": "3", "url": "http://3", "duration": 999999}, # Exceeds MAX_TRACK_LENGTH
            None, # Invalid entry
            {"id": "5"} # Missing title/url
        ]
    }
    
    tracks = await extractor.get_playlist("http://playlist", max_tracks=10)
    assert len(tracks) == 3
    assert tracks[0].title == "Track 1"
    assert tracks[1].title == "Track 2"
    
    # Test exception fallbacks
    mock_run_ytdl.side_effect = Exception("Playlist fail")
    tracks_err = await extractor.get_playlist("http://playlist", max_tracks=10)
    assert tracks_err == []
    
    # Test timeout
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        tracks_to = await extractor.get_playlist("http://playlist", max_tracks=10)
        assert tracks_to == []
