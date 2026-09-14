import os
import tempfile
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from storage.engagement_db import EngagementDB

@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_engagemind.db")
    db = EngagementDB(db_path=db_file)
    yield db
    if os.path.exists(db_file):
        os.remove(db_file)

def test_initial_db_state(temp_db):
    stats = temp_db.get_stats_today()
    assert stats["comments_count"] == 0
    assert stats["remaining"] > 0

def test_record_and_prevent_duplicate_post(temp_db):
    url = "https://www.linkedin.com/feed/update/urn:li:activity:1234567890/?utm_source=share"
    author = "Andrej Karpathy"
    comment = "Interesting insight on test-time compute scaling."

    assert temp_db.is_post_already_engaged(url) is False

    success = temp_db.record_engagement(
        post_url=url,
        author_name=author,
        comment_text=comment,
        status="COPIED"
    )
    assert success is True

    # Now it should be detected as engaged even with different query params
    url_variant = "https://www.linkedin.com/feed/update/urn:li:activity:1234567890/?trackingId=abc"
    assert temp_db.is_post_already_engaged(url_variant) is True

    # Daily count incremented
    stats = temp_db.get_stats_today()
    assert stats["comments_count"] == 1

def test_anti_stalking_author_cooldown(temp_db):
    author = "Yann LeCun"
    url1 = "https://www.linkedin.com/feed/update/urn:li:activity:111"
    url2 = "https://www.linkedin.com/feed/update/urn:li:activity:222"

    assert temp_db.is_author_recently_engaged(author) is False

    temp_db.record_engagement(post_url=url1, author_name=author, comment_text="Test", status="COPIED")
    assert temp_db.is_author_recently_engaged(author, days=14) is True

    # Different author is NOT blocked
    assert temp_db.is_author_recently_engaged("Simon Willison", days=14) is False

def test_daily_ceiling_enforcement(temp_db):
    max_daily = 3
    for i in range(max_daily):
        allowed, reason = temp_db.can_engage_now(max_daily=max_daily, cooldown_mins=0, start_hour=0, end_hour=24)
        assert allowed is True
        temp_db.record_engagement(
            post_url=f"https://linkedin.com/post/{i}",
            author_name=f"Author {i}",
            comment_text="Insight",
            status="COPIED"
        )

    # Now 4th attempt should be blocked
    allowed, reason = temp_db.can_engage_now(max_daily=max_daily, cooldown_mins=0, start_hour=0, end_hour=24)
    assert allowed is False
    assert "Daily limit reached" in reason

def test_working_hours_policy(temp_db):
    tz = ZoneInfo("Africa/Cairo")
    current_hour = datetime.now(tz).hour

    # Test when window strictly excludes current hour
    excluded_start = (current_hour + 2) % 24
    excluded_end = (current_hour + 4) % 24
    allowed, reason = temp_db.can_engage_now(start_hour=excluded_start, end_hour=excluded_end)
    assert allowed is False
    assert "Outside active hours" in reason
