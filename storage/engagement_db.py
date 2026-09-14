import os
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from zoneinfo import ZoneInfo

from config.settings import settings

logger = logging.getLogger(__name__)

class EngagementDB:
    """
    Persistence layer for EngageMind AI.
    Enforces strict daily comment quotas, anti-spam cooldowns, working hours checks,
    and prevents re-engaging the same post or same author within 14 days.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_tables()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Engaged Posts History
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS engaged_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_url TEXT UNIQUE NOT NULL,
                    post_urn TEXT,
                    author_name TEXT NOT NULL,
                    author_headline TEXT,
                    post_snippet TEXT,
                    selected_style TEXT,
                    comment_text TEXT NOT NULL,
                    mode TEXT NOT NULL,          -- 'copilot' or 'stealth'
                    status TEXT NOT NULL,        -- 'COPIED', 'POSTED', 'SKIPPED'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Daily Counters for strict rate-limiting
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_activity (
                    date_str TEXT PRIMARY KEY,
                    comments_count INTEGER DEFAULT 0,
                    last_comment_at TIMESTAMP
                );
            """)
            conn.commit()

    def _get_local_now(self) -> datetime:
        tz = ZoneInfo(settings.timezone)
        return datetime.now(tz)

    def can_engage_now(
        self,
        max_daily: Optional[int] = None,
        cooldown_mins: Optional[int] = None,
        start_hour: Optional[int] = None,
        end_hour: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Evaluates whether a new comment is permitted right now against all safety policies:
        1. Working hours check (09:00 AM - 07:00 PM).
        2. Daily hard ceiling (default 4 comments/day).
        3. Minimum interval between comments (default 60 minutes).
        Returns (is_allowed, reason).
        """
        max_daily = max_daily if max_daily is not None else settings.max_comments_per_day
        cooldown_mins = cooldown_mins if cooldown_mins is not None else settings.min_cooldown_minutes
        start_hour = start_hour if start_hour is not None else settings.active_hours_start
        end_hour = end_hour if end_hour is not None else settings.active_hours_end

        local_now = self._get_local_now()
        date_str = local_now.strftime("%Y-%m-%d")

        # 1. Working Hours Policy
        if local_now.hour < start_hour or local_now.hour >= end_hour:
            return False, f"Outside active hours ({start_hour}:00 - {end_hour}:00). Current time: {local_now.strftime('%H:%M')}."

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT comments_count, last_comment_at FROM daily_activity WHERE date_str = ?", (date_str,))
            row = cursor.fetchone()

            if not row:
                return True, "First comment of the day. Permitted."

            count = row["comments_count"]
            last_ts_str = row["last_comment_at"]

            # 2. Daily Limit Policy
            if count >= max_daily:
                return False, f"Daily limit reached ({count}/{max_daily} comments for {date_str})."

            # 3. Cooldown Interval Policy
            if last_ts_str:
                try:
                    last_ts = datetime.fromisoformat(last_ts_str)
                    if last_ts.tzinfo is None:
                        last_ts = last_ts.replace(tzinfo=ZoneInfo(settings.timezone))
                    elapsed = (local_now - last_ts).total_seconds() / 60.0
                    if elapsed < cooldown_mins:
                        remaining = int(cooldown_mins - elapsed)
                        return False, f"Cooldown active. {remaining}m remaining before next comment."
                except Exception as ex:
                    logger.debug(f"Error parsing last_comment_at: {ex}")

        return True, "Safety checks passed. Engagement permitted."

    def is_post_already_engaged(self, post_url: str) -> bool:
        """Returns True if this exact post URL has already been reviewed or engaged."""
        clean_url = post_url.split("?")[0].strip().rstrip("/")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM engaged_posts WHERE post_url LIKE ?", (f"{clean_url}%",))
            return cursor.fetchone() is not None

    def is_author_recently_engaged(self, author_name: str, days: int = 14) -> bool:
        """Avoids commenting on the same person's posts within N days."""
        if not author_name or author_name.strip() == "":
            return False

        cutoff = (self._get_local_now() - timedelta(days=days)).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM engaged_posts WHERE LOWER(author_name) = LOWER(?) AND created_at >= ?",
                (author_name.strip(), cutoff)
            )
            return cursor.fetchone() is not None

    def record_engagement(
        self,
        post_url: str,
        author_name: str,
        comment_text: str,
        selected_style: str = "tradeoff",
        author_headline: Optional[str] = None,
        post_snippet: Optional[str] = None,
        mode: str = "copilot",
        status: str = "COPIED"
    ) -> bool:
        """Records an engaged post and increments the daily counter."""
        local_now = self._get_local_now()
        date_str = local_now.strftime("%Y-%m-%d")
        now_iso = local_now.isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO engaged_posts (
                        post_url, author_name, author_headline, post_snippet,
                        selected_style, comment_text, mode, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    post_url.strip(), author_name.strip(), author_headline or "",
                    post_snippet or "", selected_style, comment_text.strip(),
                    mode, status, now_iso
                ))

                # Increment daily counter only if actually copied or posted
                if status in ["COPIED", "POSTED"]:
                    cursor.execute("""
                        INSERT INTO daily_activity (date_str, comments_count, last_comment_at)
                        VALUES (?, 1, ?)
                        ON CONFLICT(date_str) DO UPDATE SET
                            comments_count = comments_count + 1,
                            last_comment_at = excluded.last_comment_at
                    """, (date_str, now_iso))

                conn.commit()
                return True
            except sqlite3.IntegrityError:
                logger.warning(f"Post already exists in engagement DB: {post_url}")
                return False

    def get_stats_today(self) -> Dict[str, Any]:
        """Returns statistics for today's activity."""
        local_now = self._get_local_now()
        date_str = local_now.strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT comments_count, last_comment_at FROM daily_activity WHERE date_str = ?", (date_str,))
            row = cursor.fetchone()
            count = row["comments_count"] if row else 0
            last_at = row["last_comment_at"] if row else None
            return {
                "date": date_str,
                "comments_count": count,
                "max_allowed": settings.max_comments_per_day,
                "last_comment_at": last_at,
                "remaining": max(0, settings.max_comments_per_day - count)
            }
