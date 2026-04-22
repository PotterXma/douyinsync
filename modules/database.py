import sys
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

from modules.logger import logger
from utils.models import VideoRecord

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_FILE = PROJECT_ROOT / "douyinsync.db"

class DatabaseConnectionError(Exception):
    """Specific exception raised when the database connection fails or cannot be initialized."""
    pass

class AppDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._initialize_db()
        
    def _initialize_db(self) -> None:
        """Ensures the sqlite database file exists and PRAGMAs are set."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                # Use a larger busy timeout to avoid 'database is locked' errors
                cursor.execute("PRAGMA busy_timeout=10000;")
                self._create_tables(cursor)
                journal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
                logger.debug("Database initialized. Journal mode: %s", journal_mode)
        except OSError as e:
            logger.critical("Failed to access database file at %s: %s", self.db_path, e)
            raise DatabaseConnectionError(f"Failed to access database file: {e}")
        except sqlite3.Error as e:
            logger.critical("SQLite error during initialization: %s", e)
            raise DatabaseConnectionError(f"SQLite error during initialization: {e}")
            
    def _create_tables(self, cursor: sqlite3.Cursor) -> None:
        """Creates required schemas if they do not exist."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                douyin_id TEXT PRIMARY KEY,
                account_mark TEXT,
                title TEXT,
                description TEXT,
                video_url TEXT,
                cover_url TEXT,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                local_video_path TEXT,
                local_cover_path TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        """)
            
    @contextmanager
    def get_connection(self):
        """Context manager for yielding a tracked sqlite connection."""
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path, 
                timeout=10.0, 
                isolation_level=None  # autocommit mode, transactions explicitly managed
            )
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            logger.error("Failed to connect to SQLite DB: %s", e)
            raise DatabaseConnectionError(f"Connection failed: {e}")
        finally:
            if conn:
                conn.close()

db = AppDatabase(DB_FILE)

class VideoDAO:
    """Data Access Object wrapper for handling specific domain queries over AppDatabase."""
    
    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> VideoRecord:
        """Helper to safely map a sqlite row to a VideoRecord."""
        return VideoRecord(
            douyin_id=row['douyin_id'],
            account_mark=row['account_mark'],
            title=row['title'],
            description=row['description'],
            video_url=row['video_url'],
            cover_url=row['cover_url'],
            status=row['status'],
            retry_count=row['retry_count'],
            local_video_path=row['local_video_path'],
            local_cover_path=row['local_cover_path'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    @staticmethod
    def insert_video_if_unique(record: VideoRecord) -> bool:
        """
        Idempotent insert. Ignores if douyin_id already exists.
        Returns True if a new row was inserted, False if it was completely ignored.
        """
        sql = """
            INSERT OR IGNORE INTO videos (
                douyin_id, account_mark, title, description, video_url, cover_url,
                status, retry_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        now = int(time.time())
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (
                record.douyin_id,
                record.account_mark,
                record.title,
                record.description,
                record.video_url,
                record.cover_url,
                record.status,
                record.retry_count,
                now,
                now
            ))
            return cursor.rowcount > 0

    @staticmethod
    def update_status(douyin_id: str, new_status: str, extra_updates: dict = None) -> None:
        """Updates the tracking status of a video document."""
        if extra_updates is None:
            extra_updates = {}
        
        updates = ["status = ?", "updated_at = ?"]
        now = int(time.time())
        params = [new_status, now]
        
        for k, v in extra_updates.items():
            updates.append(f"{k} = ?")
            params.append(v)
            
        params.append(douyin_id)
        
        sql = f"UPDATE videos SET {', '.join(updates)} WHERE douyin_id = ?"
        
        with db.get_connection() as conn:
            conn.execute(sql, tuple(params))

    @staticmethod
    def get_pending_videos(limit: int = 5) -> list[VideoRecord]:
        """Retrieves outstanding elements marked as 'pending' mapping them back to VideoRecord."""
        sql = "SELECT * FROM videos WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?"
        results = []
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for row in cursor.execute(sql, (limit,)):
                results.append(VideoDAO._row_to_record(row))
        return results

    @staticmethod
    def get_uploadable_videos(limit: int = 1) -> list[VideoRecord]:
        """
        Retrieves videos that were downloaded but failed to upload (status='downloaded' or 'failed' with local paths).
        Only returns videos with retry_count < 3 to prevent infinite retry loops.
        """
        sql = """
            SELECT *
            FROM videos 
            WHERE ((status = 'downloaded') OR (status = 'failed' AND local_video_path IS NOT NULL AND local_video_path != ''))
              AND retry_count < 3
            ORDER BY updated_at ASC LIMIT ?
        """
        results = []
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for row in cursor.execute(sql, (limit,)):
                results.append(VideoDAO._row_to_record(row))
        return results

    @staticmethod
    def get_uploaded_today_count() -> int:
        """Counts how many videos successfully uploaded locally today (timezone handled purely via python logic or naive for int)."""
        # We need a proper way to count today but since we use INTEGER timestamps, 
        # it's best to compute start of day locally and use >= start_of_day.
        # Since this involves timezone and sqlite integer representation 
        current_time_str = time.strftime('%Y-%m-%d')
        # However, to avoid python-only overhead, if we convert unix timestamp to local ISO, we can match
        # date(datetime(updated_at, 'unixepoch', 'localtime')) == date('now', 'localtime')
        sql = "SELECT COUNT(*) FROM videos WHERE status = 'uploaded' AND date(datetime(updated_at, 'unixepoch', 'localtime')) = date('now', 'localtime')"
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            return cursor.fetchone()[0]

    @staticmethod
    def revert_zombies() -> int:
        """
        Self-Healing Mechanism (Story 4.4):
        Locates any rows left 'processing' upon shutdown, reverting them so they aren't totally lost.
        """
        now = int(time.time())
        sql_revert_processing = """
            UPDATE videos 
            SET status = 'pending', retry_count = retry_count + 1, updated_at = ?
            WHERE status = 'processing' OR status = 'downloading'
        """
        sql_revert_uploading = """
            UPDATE videos
            SET status = 'downloaded', retry_count = retry_count + 1, updated_at = ?
            WHERE status = 'uploading'
        """
        sql_fail_loop = """
            UPDATE videos
            SET status = 'give_up_fatal', updated_at = ?
            WHERE status = 'pending' AND retry_count >= 3
        """
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_revert_processing, (now,))
            reverted = cursor.rowcount
            cursor.execute(sql_revert_uploading, (now,))
            reverted += cursor.rowcount
            cursor.execute(sql_fail_loop, (now,))
            
            return reverted

    @staticmethod
    def update_fresh_urls(douyin_id: str, video_url: str, cover_url: str) -> None:
        """Updates cached CDN URLs with fresh ones to prevent stale token 403 errors."""
        sql = "UPDATE videos SET video_url = ?, cover_url = ?, updated_at = ? WHERE douyin_id = ?"
        now = int(time.time())
        with db.get_connection() as conn:
            conn.execute(sql, (video_url, cover_url, now, douyin_id))

    @staticmethod
    def get_pipeline_stats() -> dict[str, int]:
        """Retrieves aggregated statistics of videos grouped by current status using a safe polling query."""
        sql = "SELECT status, COUNT(*) as count FROM videos GROUP BY status"
        stats = {}
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for row in cursor.execute(sql):
                stats[row['status']] = row['count']
        return stats

