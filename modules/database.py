import sys
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from modules.logger import logger

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_FILE = PROJECT_ROOT / "douyinsync.db"

class DBManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._initialize_db()
        
    def _initialize_db(self):
        """Ensures the sqlite database file exists and PRAGMAs are set."""
        try:
            with self.get_connection() as conn:
                # Setup WAL Mode for high concurrency reads/writes
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                # Use a larger busy timeout to avoid 'database is locked' errors
                cursor.execute("PRAGMA busy_timeout=10000;")
                self._create_tables(cursor)
                journal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
                logger.debug(f"Database initialized. Journal mode: {journal_mode}")
        except OSError as e:
            logger.critical(f"Failed to access database file at {self.db_path}: {e}")
            raise
            
    def _create_tables(self, cursor):
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
            
    @contextmanager
    def get_connection(self):
        """Context manager for yielding a tracked sqlite connection."""
        conn = None
        try:
            # timeout parameter prevents locking during concurrent UI/Background polling
            conn = sqlite3.connect(
                self.db_path, 
                timeout=10.0, 
                isolation_level=None  # autocommit mode, transactions must be explicitly managed if needed
            )
            # Fetch as dicts for easier consumption
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            if conn:
                conn.close()

db = DBManager(DB_FILE)

class VideoDAO:
    """Data Access Object wrapper for handling specific domain queries over DBManager."""
    @staticmethod
    def insert_video_if_unique(video_data: dict) -> bool:
        """
        Idempotent insert. Ignores if douyin_id already exists.
        Returns True if a new row was inserted, False if it was completely ignored.
        """
        sql = """
            INSERT OR IGNORE INTO videos (
                douyin_id, account_mark, title, description, video_url, cover_url
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (
                video_data.get('douyin_id'),
                video_data.get('account_mark', ''),
                video_data.get('title', ''),
                video_data.get('description', ''),
                video_data.get('video_url', ''),
                video_data.get('cover_url', '')
            ))
            return cursor.rowcount > 0

    @staticmethod
    def update_status(douyin_id: str, new_status: str, extra_updates: dict = None) -> None:
        """Updates the tracking status of a video document."""
        if extra_updates is None:
            extra_updates = {}
        
        updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params = [new_status]
        
        for k, v in extra_updates.items():
            updates.append(f"{k} = ?")
            params.append(v)
            
        params.append(douyin_id)
        
        sql = f"UPDATE videos SET {', '.join(updates)} WHERE douyin_id = ?"
        
        with db.get_connection() as conn:
            conn.execute(sql, tuple(params))

    @staticmethod
    def get_pending_videos(limit: int = 5) -> list:
        """Retrieves outstanding elements marked as 'pending' mapping them back to python dicts."""
        sql = "SELECT douyin_id, title, description, video_url, cover_url FROM videos WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?"
        results = []
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for row in cursor.execute(sql, (limit,)):
                results.append({
                    'douyin_id': row[0],
                    'title': row[1],
                    'description': row[2],
                    'video_url': row[3],
                    'cover_url': row[4]
                })
        return results

    @staticmethod
    def get_uploaded_today_count() -> int:
        """Counts how many videos successfully uploaded locally today."""
        sql = "SELECT COUNT(*) FROM videos WHERE status = 'uploaded' AND date(updated_at, 'localtime') = date('now', 'localtime')"
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
        sql = """
            UPDATE videos 
            SET status = 'pending', retry_count = retry_count + 1, updated_at = CURRENT_TIMESTAMP 
            WHERE status = 'processing' OR status = 'downloading' OR status = 'uploading'
        """
        sql_fail_loop = """
            UPDATE videos
            SET status = 'give_up_fatal', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'pending' AND retry_count >= 3
        """
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            reverted = cursor.rowcount
            # Apply infinite loop defense limit
            cursor.execute(sql_fail_loop)
            
            return reverted
