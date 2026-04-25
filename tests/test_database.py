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
