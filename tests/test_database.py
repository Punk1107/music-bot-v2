import asyncio
import pytest

from core.database import DatabaseManager
from models.track import Track

@pytest.fixture
async def db_manager():
    db = DatabaseManager(db_path=":memory:")
    # initialise creates the tables so we can run tests
    await db.initialise()
    yield db
    await db.close()

@pytest.fixture
def sample_track():
    return Track(
        title="DB Test Track",
        url="https://youtube.com/watch?v=db",
        duration=250,
        thumbnail="thumb.jpg",
        uploader="DB Uploader",
        view_count=5000,
        upload_date="20240101"
    )

@pytest.mark.asyncio
async def test_database_fallback_connect():
    """Test fallback connection logic when initialise() is not called yet. Covers 122-124, 136-145"""
    db = DatabaseManager(db_path=":memory:")
    # We deliberately don't call initialise() to trigger fallback.
    # To avoid erroring out because schema doesn't exist, we just run a basic SELECT.
    async with db._connect() as conn:
        res = await conn.execute("SELECT 1")
        assert await res.fetchone() is not None
    await db.close()

@pytest.mark.asyncio
async def test_record_track_played(db_manager, sample_track):
    """Test record_track_played history insertion and stat incrementation. Covers 244-269"""
    guild_id = 111
    user_id = 222
    duration = 150
    
    await db_manager.record_track_played(
        guild_id=guild_id,
        user_id=user_id,
        track=sample_track,
        duration_played=duration,
        skipped=False,
        completed=True
    )
    
    # Verify History
    history = await db_manager.get_history(guild_id)
    assert len(history) == 1
    assert history[0]["track"].title == sample_track.title
    assert history[0]["completed"] is True
    
    # Verify User Stats Upsert
    stats = await db_manager.get_user_stats(guild_id, user_id)
    assert stats is not None
    assert stats["total_tracks_requested"] == 1
    assert stats["total_listening_time"] == duration

@pytest.mark.asyncio
async def test_analytics(db_manager):
    """Test analytics logging and retrieval. Covers 500-530"""
    guild_id = 555
    event_type = "test_event"
    payload = {"some_key": "some_value", "nested": [1, 2, 3]}
    
    # Log event
    await db_manager.log_event(guild_id, event_type, payload)
    
    # Test Retrieval with event type filter
    events_filtered = await db_manager.get_analytics(guild_id, event_type=event_type)
    assert len(events_filtered) == 1
    assert events_filtered[0]["event_type"] == event_type
    assert events_filtered[0]["payload"]["some_key"] == "some_value"
    
    # Test Retrieval without event type filter
    events_unfiltered = await db_manager.get_analytics(guild_id)
    assert len(events_unfiltered) == 1
    assert events_unfiltered[0]["event_type"] == event_type
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.database import DatabaseManager
from models.track import Track

@pytest.mark.asyncio
async def test_save_queue():
    """Test saving a queue to the database. Covers lines 189-202"""
    db = DatabaseManager(":memory:")
    await db.initialise()
    
    tracks = [
        Track("T1", "http://1", 100, None, "U1", requester_id=111),
        Track("T2", "http://2", 200, None, "U2", requester_id=222)
    ]
    
    await db.save_queue(123, 456, tracks)
    
    loaded_tracks = await db.load_queue(123)
    assert len(loaded_tracks) == 2
    assert loaded_tracks[0].title == "T1"
    assert loaded_tracks[1].title == "T2"

@pytest.mark.asyncio
async def test_log_search_query():
    """Test logging search queries. Covers lines 401-420"""
    db = DatabaseManager(":memory:")
    await db.initialise()
    
    await db.save_search_query(123, 456, "q1")
    await db.save_search_query(123, 456, "q2")
    
    # Empty query should do nothing
    await db.save_search_query(123, 456, "")
    await db.save_search_query(123, 456, "a") # < 2
    
    # We don't have a get method for this, so we'll just check it doesn't crash
    # To test the PURGE logic, we can insert 201 records
    for i in range(205):
        await db.save_search_query(123, 456, f"query {i}")

@pytest.mark.asyncio
async def test_get_top_tracks():
    """Test get_top_tracks fetching logic. Covers lines 542-567"""
    db = DatabaseManager(":memory:")
    await db.initialise()
    
    t1 = Track("Pop", "http://pop", 100, None, "U1", requester_id=1)
    t2 = Track("Rock", "http://rock", 100, None, "U1", requester_id=1)
    
    # Record history
    await db.record_track_played(123, 456, t1)
    await db.record_track_played(123, 456, t1)
    await db.record_track_played(123, 456, t2)
    
    # Test valid fetch
    results = await db.get_top_tracks(123, days=7, limit=10)
    assert len(results) == 2
    assert results[0]["title"] == "Pop"
    assert results[0]["play_count"] == 2
    assert results[1]["title"] == "Rock"
    assert results[1]["play_count"] == 1
    
    # Test empty fetch
    results_empty = await db.get_top_tracks(999, days=7, limit=10)
    assert len(results_empty) == 0
