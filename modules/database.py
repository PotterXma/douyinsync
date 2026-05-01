import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Optional

from modules.logger import logger
from utils.models import VideoRecord
from utils.paths import data_root

DB_FILE = data_root() / "douyinsync.db"

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
                self._migrate_videos_columns(cursor)
                conn.commit()
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

    def _migrate_videos_columns(self, cursor: sqlite3.Cursor) -> None:
        """Additive schema upgrades for Epic 5 upload progress (5-5)."""
        cursor.execute("PRAGMA table_info(videos)")
        existing = {row[1] for row in cursor.fetchall()}
        specs = [
            ("upload_bytes_done", "INTEGER NOT NULL DEFAULT 0"),
            ("upload_bytes_total", "INTEGER"),
            ("last_error_summary", "TEXT"),
            ("youtube_video_id", "TEXT"),
        ]
        for col, decl in specs:
            if col not in existing:
                cursor.execute("ALTER TABLE videos ADD COLUMN %s %s" % (col, decl))

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
    def _col(row: sqlite3.Row, key: str, default: Any = None) -> Any:
        keys = row.keys()
        if key not in keys:
            return default
        v = row[key]
        return default if v is None else v

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> VideoRecord:
        """Helper to safely map a sqlite row to a VideoRecord."""
        return VideoRecord(
            douyin_id=row["douyin_id"],
            account_mark=row["account_mark"],
            title=row["title"],
            description=row["description"],
            video_url=row["video_url"],
            cover_url=row["cover_url"],
            status=row["status"],
            retry_count=row["retry_count"],
            local_video_path=row["local_video_path"],
            local_cover_path=row["local_cover_path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            upload_bytes_done=int(VideoDAO._col(row, "upload_bytes_done", 0) or 0),
            upload_bytes_total=VideoDAO._col(row, "upload_bytes_total", None),
            last_error_summary=VideoDAO._col(row, "last_error_summary", None),
            youtube_video_id=VideoDAO._col(row, "youtube_video_id", None),
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
    def get_uploadable_videos(limit: int = 1, *, ignore_retry_cap: bool = False) -> list[VideoRecord]:
        """
        Retrieves videos that were downloaded but failed to upload (status='downloaded' or 'failed' with local paths).

        Unless ``ignore_retry_cap`` is True, ``AND retry_count < 3`` applies to the **entire** WHERE clause, so both
        ``downloaded`` and ``failed`` rows with high ``retry_count`` are excluded. When True, that filter is removed
        (e.g. force manual retry cycle).
        """
        retry_filter = "" if ignore_retry_cap else "AND retry_count < 3"
        sql = f"""
            SELECT *
            FROM videos 
            WHERE ((status = 'downloaded') OR (status = 'failed' AND local_video_path IS NOT NULL AND local_video_path != ''))
              {retry_filter}
            ORDER BY updated_at ASC LIMIT ?
        """
        results = []
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for row in cursor.execute(sql, (limit,)):
                results.append(VideoDAO._row_to_record(row))
        return results

    @staticmethod
    def prepare_for_force_manual_retry() -> int:
        """
        Normalize exhausted or high-retry rows so a **force manual** pipeline pass can:
        - re-download then upload when there is no usable local file, and
        - re-upload when a local file is still present.

        Returns the total number of rows updated (sum of statement rowcounts).

        Runs inside a single ``BEGIN IMMEDIATE`` transaction so either all four UPDATEs apply or none.
        """
        now = int(time.time())
        with db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                total = 0
                cur = conn.execute(
                    """
                    UPDATE videos
                    SET status = 'downloaded', retry_count = 0, updated_at = ?
                    WHERE status IN ('give_up', 'give_up_fatal')
                      AND local_video_path IS NOT NULL AND TRIM(local_video_path) != ''
                    """,
                    (now,),
                )
                total += cur.rowcount
                cur = conn.execute(
                    """
                    UPDATE videos
                    SET status = 'pending', retry_count = 0, updated_at = ?,
                        local_video_path = NULL, local_cover_path = NULL
                    WHERE status IN ('give_up', 'give_up_fatal')
                      AND (local_video_path IS NULL OR TRIM(local_video_path) = '')
                    """,
                    (now,),
                )
                total += cur.rowcount
                cur = conn.execute(
                    """
                    UPDATE videos
                    SET status = 'downloaded', retry_count = 0, updated_at = ?
                    WHERE status = 'failed'
                      AND local_video_path IS NOT NULL AND TRIM(local_video_path) != ''
                    """,
                    (now,),
                )
                total += cur.rowcount
                cur = conn.execute(
                    """
                    UPDATE videos
                    SET status = 'pending', retry_count = 0, updated_at = ?,
                        local_video_path = NULL, local_cover_path = NULL
                    WHERE status = 'failed'
                      AND (local_video_path IS NULL OR TRIM(local_video_path) = '')
                    """,
                    (now,),
                )
                total += cur.rowcount
                conn.commit()
                return total
            except Exception:
                conn.rollback()
                raise

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
    def count_uploaded_for_account(account_mark: Optional[str]) -> int:
        """
        同一 ``account_mark`` 下当前 ``status='uploaded'`` 的行数。
        下一条即将上传的封面序号 = 返回值 + 1（本行尚未写入 uploaded 时调用）。
        """
        mark = account_mark or ""
        sql = (
            "SELECT COUNT(*) FROM videos WHERE status = 'uploaded' "
            "AND IFNULL(account_mark, '') = ?"
        )
        with db.get_connection() as conn:
            row = conn.execute(sql, (mark,)).fetchone()
            return int(row[0]) if row else 0

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
            SET status = 'downloaded', retry_count = retry_count + 1, updated_at = ?,
                upload_bytes_done = 0, upload_bytes_total = NULL, last_error_summary = NULL
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
    def update_upload_progress(douyin_id: str, done: int, total: Optional[int]) -> None:
        """Throttle caller should gate frequency; always refreshes ``updated_at`` for HUD ordering."""
        now = int(time.time())
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE videos SET upload_bytes_done = ?, upload_bytes_total = ?, updated_at = ? WHERE douyin_id = ?",
                (max(0, int(done)), total, now, douyin_id),
            )

    @staticmethod
    def get_active_pipeline_video() -> Optional[dict[str, Any]]:
        """
        Single active row for Dashboard (PRD): earliest ``uploading`` by ``updated_at``,
        else earliest ``downloading`` / ``processing``.
        """
        with db.get_connection() as conn:
            cur = conn.cursor()
            row = cur.execute(
                """
                SELECT douyin_id, title, account_mark, status,
                       upload_bytes_done, upload_bytes_total, updated_at
                FROM videos WHERE status = 'uploading'
                ORDER BY updated_at ASC LIMIT 1
                """
            ).fetchone()
            if not row:
                row = cur.execute(
                    """
                    SELECT douyin_id, title, account_mark, status,
                           upload_bytes_done, upload_bytes_total, updated_at
                    FROM videos WHERE status IN ('downloading', 'processing')
                    ORDER BY updated_at ASC LIMIT 1
                    """
                ).fetchone()
            if not row:
                return None
            return {
                "douyin_id": row["douyin_id"],
                "title": row["title"] or "",
                "account_mark": row["account_mark"] or "",
                "status": row["status"],
                "upload_bytes_done": int(row["upload_bytes_done"] or 0),
                "upload_bytes_total": row["upload_bytes_total"],
                "updated_at": row["updated_at"],
            }

    @staticmethod
    def get_latest_uploaded_snapshot() -> Optional[dict[str, Any]]:
        """Most recently uploaded row (for Dashboard «recent success» line)."""
        sql = """
            SELECT douyin_id, title, account_mark, youtube_video_id, updated_at
            FROM videos WHERE status = 'uploaded'
            ORDER BY updated_at DESC LIMIT 1
        """
        with db.get_connection() as conn:
            row = conn.cursor().execute(sql).fetchone()
            if not row:
                return None
            return {
                "douyin_id": row["douyin_id"],
                "title": row["title"] or "",
                "account_mark": row["account_mark"] or "",
                "youtube_video_id": row["youtube_video_id"] or "",
                "updated_at": row["updated_at"],
            }

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

    @staticmethod
    def get_accounts_pipeline_stats() -> dict[str, dict[str, int]]:
        """
        Per-account status counts for Epic 5 dashboard cards.
        Keys are account_mark (empty/NULL -> 'Unknown'); inner keys are status -> count.
        """
        sql = """
            SELECT account_mark, status, COUNT(*) AS cnt
            FROM videos
            GROUP BY account_mark, status
        """
        out: dict[str, dict[str, int]] = {}
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for row in cursor.execute(sql):
                mark = (row["account_mark"] or "").strip() or "Unknown"
                st = row["status"]
                out.setdefault(mark, {})[st] = row["cnt"]
        return out

    @staticmethod
    def get_recent_failure_rows(limit: int = 25) -> list[dict[str, object]]:
        """
        Recent failed / give-up rows for dashboard failure panel (read-only UI).
        """
        sql = """
            SELECT douyin_id, title, account_mark, status, retry_count, local_video_path, updated_at
            FROM videos
            WHERE status IN ('failed', 'give_up', 'give_up_fatal')
            ORDER BY updated_at DESC
            LIMIT ?
        """
        rows: list[dict[str, object]] = []
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for row in cursor.execute(sql, (limit,)):
                rows.append(
                    {
                        "douyin_id": row["douyin_id"],
                        "title": (row["title"] or "")[:80],
                        "account_mark": row["account_mark"] or "Unknown",
                        "status": row["status"],
                        "retry_count": row["retry_count"],
                        "local_video_path": row["local_video_path"] or "",
                        "updated_at": row["updated_at"],
                    }
                )
        return rows

    @staticmethod
    def list_videos_for_library(filter_status: Optional[str] = None, limit: int = 500) -> list[tuple]:
        """
        Classic videolib Treeview rows:
        (douyin_id, status, account_mark, retry_count, title, local_video_path, updated_at,
        upload_bytes_done, upload_bytes_total, last_error_summary, youtube_video_id).
        ``updated_at`` is Unix seconds; UI can format as Beijing wall time.
        ``filter_status`` is an exact DB status value, or None for all rows.
        """
        sql = (
            "SELECT douyin_id, status, account_mark, retry_count, title, local_video_path, updated_at, "
            "COALESCE(upload_bytes_done, 0), upload_bytes_total, last_error_summary, youtube_video_id "
            "FROM videos"
        )
        params: list = []
        if filter_status:
            sql += " WHERE status = ?"
            params.append(filter_status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with db.get_connection() as conn:
            cur = conn.execute(sql, tuple(params))
            return [tuple(row) for row in cur.fetchall()]

    @staticmethod
    def bulk_reset_to_pending(douyin_ids: list[str]) -> int:
        """
        Sets ``status=pending`` and ``retry_count=0``; clears operator-visible/error/UI carry-over fields
        so the next pipeline pass starts clean (``last_error_summary``, upload progress, stale YouTube id).
        """
        if not douyin_ids:
            return 0
        now = int(time.time())
        placeholders = ",".join("?" * len(douyin_ids))
        sql = (
            f"UPDATE videos SET status = 'pending', retry_count = 0, updated_at = ?, "
            f"last_error_summary = NULL, upload_bytes_done = 0, upload_bytes_total = NULL, "
            f"youtube_video_id = NULL "
            f"WHERE douyin_id IN ({placeholders})"
        )
        params: tuple = (now, *douyin_ids)
        with db.get_connection() as conn:
            cur = conn.execute(sql, params)
            return cur.rowcount

