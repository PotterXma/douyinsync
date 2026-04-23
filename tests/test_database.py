import unittest
import sqlite3
import time
from pathlib import Path
import tempfile
import shutil

import modules.database as db_module
from modules.database import VideoDAO, DatabaseConnectionError, AppDatabase
from utils.models import VideoRecord

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_douyinsync.db"
        
        # Override global DBManager for isolated testing
        db_module.db = AppDatabase(self.db_path)
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def test_wal_mode_and_schema(self):
        """Test that WAL journaling is enabled and schema uses integer timestamps."""
        with db_module.db.get_connection() as conn:
            cursor = conn.cursor()
            journal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
            self.assertEqual(journal_mode.lower(), "wal")
            
            # Check schema for integer timestamp
            cursor.execute("PRAGMA table_info(videos);")
            columns = {row['name']: row['type'] for row in cursor.fetchall()}
            self.assertEqual(columns.get('created_at', '').upper(), 'INTEGER')
            self.assertEqual(columns.get('updated_at', '').upper(), 'INTEGER')
        
    def test_insert_video_if_unique(self):
        test_video = VideoRecord(
            douyin_id="TEST_001",
            account_mark="TEST_ACCOUNT",
            title="Test Title",
            description="Test Desc",
            video_url="http://vid",
            cover_url="http://cover"
        )
        
        is_new = VideoDAO.insert_video_if_unique(test_video)
        self.assertTrue(is_new, "First insert should be treated as new.")
        
        is_new2 = VideoDAO.insert_video_if_unique(test_video)
        self.assertFalse(is_new2, "Duplicate insert should be ignored.")
        
    def test_get_pending_videos(self):
        test_video = VideoRecord(
            douyin_id="TEST_002",
            account_mark="TEST_ACCOUNT",
            title="Test Title 2",
            description="Test Desc 2",
            video_url="http://vid2",
            cover_url="http://cover2"
        )
        VideoDAO.insert_video_if_unique(test_video)
        
        pending_list = VideoDAO.get_pending_videos(limit=5)
        self.assertEqual(len(pending_list), 1)
        self.assertIsInstance(pending_list[0], VideoRecord)
        self.assertEqual(pending_list[0].douyin_id, "TEST_002")

    def test_update_status(self):
        test_video = VideoRecord(
            douyin_id="TEST_003",
            account_mark="TEST_ACCOUNT"
        )
        VideoDAO.insert_video_if_unique(test_video)
        
        extra_updates = {"local_video_path": "/fake/path.mp4"}
        VideoDAO.update_status("TEST_003", "downloaded", extra_updates)
        
        with db_module.db.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT status, local_video_path, updated_at FROM videos WHERE douyin_id = 'TEST_003'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['status'], 'downloaded')
            self.assertEqual(row['local_video_path'], '/fake/path.mp4')
            self.assertIsInstance(row['updated_at'], int)

    def test_get_pipeline_stats(self):
        test_video1 = VideoRecord(douyin_id="STAT_001", account_mark="A1", status="pending")
        test_video2 = VideoRecord(douyin_id="STAT_002", account_mark="A2", status="processing")
        test_video3 = VideoRecord(douyin_id="STAT_003", account_mark="A3", status="uploaded")
        test_video4 = VideoRecord(douyin_id="STAT_004", account_mark="A4", status="uploaded")
        VideoDAO.insert_video_if_unique(test_video1)
        VideoDAO.insert_video_if_unique(test_video2)
        VideoDAO.insert_video_if_unique(test_video3)
        VideoDAO.insert_video_if_unique(test_video4)

        stats = VideoDAO.get_pipeline_stats()
        self.assertEqual(stats.get("pending", 0), 1)
        self.assertEqual(stats.get("processing", 0), 1)
        self.assertEqual(stats.get("uploaded", 0), 2)

    def test_get_accounts_pipeline_stats(self):
        VideoDAO.insert_video_if_unique(
            VideoRecord(douyin_id="AC_1", account_mark="ChanA", status="pending")
        )
        VideoDAO.insert_video_if_unique(
            VideoRecord(douyin_id="AC_2", account_mark="ChanA", status="uploaded")
        )
        VideoDAO.insert_video_if_unique(
            VideoRecord(douyin_id="AC_3", account_mark="ChanB", status="failed")
        )
        VideoDAO.insert_video_if_unique(VideoRecord(douyin_id="AC_4", account_mark="", status="pending"))

        by_acct = VideoDAO.get_accounts_pipeline_stats()
        self.assertEqual(by_acct["ChanA"]["pending"], 1)
        self.assertEqual(by_acct["ChanA"]["uploaded"], 1)
        self.assertEqual(by_acct["ChanB"]["failed"], 1)
        self.assertEqual(by_acct["Unknown"]["pending"], 1)

    def test_get_recent_failure_rows(self):
        now = int(time.time())
        with db_module.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO videos (
                    douyin_id, account_mark, title, description, video_url, cover_url,
                    status, retry_count, created_at, updated_at
                ) VALUES (?, ?, ?, '', '', '', 'failed', 2, ?, ?)
                """,
                ("FAIL_1", "X", "t1", now, now),
            )
            conn.execute(
                """
                INSERT INTO videos (
                    douyin_id, account_mark, title, description, video_url, cover_url,
                    status, retry_count, created_at, updated_at
                ) VALUES (?, ?, ?, '', '', '', 'give_up_fatal', 3, ?, ?)
                """,
                ("FAIL_2", "Y", "t2", now + 1, now + 1),
            )
            conn.commit()

        rows = VideoDAO.get_recent_failure_rows(limit=10)
        self.assertGreaterEqual(len(rows), 2)
        ids = {r["douyin_id"] for r in rows}
        self.assertIn("FAIL_1", ids)
        self.assertIn("FAIL_2", ids)
        self.assertTrue(all(r["status"] in ("failed", "give_up", "give_up_fatal") for r in rows))

    def test_list_videos_for_library(self):
        VideoDAO.insert_video_if_unique(
            VideoRecord(douyin_id="LIB_ROW_1", account_mark="Acc", title="Hello", status="pending")
        )
        rows_all = VideoDAO.list_videos_for_library(filter_status=None, limit=50)
        self.assertTrue(any(r[0] == "LIB_ROW_1" for r in rows_all))
        rows_f = VideoDAO.list_videos_for_library(filter_status="pending", limit=50)
        self.assertTrue(all(r[1] == "pending" for r in rows_f))

    def test_bulk_reset_to_pending(self):
        VideoDAO.insert_video_if_unique(
            VideoRecord(douyin_id="LIB_RST_1", account_mark="Acc", title="X", status="failed", retry_count=2)
        )
        n = VideoDAO.bulk_reset_to_pending(["LIB_RST_1"])
        self.assertGreaterEqual(n, 1)
        with db_module.db.get_connection() as conn:
            row = conn.execute(
                "SELECT status, retry_count FROM videos WHERE douyin_id = ?",
                ("LIB_RST_1",),
            ).fetchone()
            self.assertEqual(row["status"], "pending")
            self.assertEqual(row["retry_count"], 0)

    def test_revert_zombies(self):
        # Insert a set of states to test
        test_data = [
            VideoRecord(douyin_id="ZOMBIE_01", account_mark="A1", status="processing"),
            VideoRecord(douyin_id="ZOMBIE_02", account_mark="A2", status="downloading"),
            VideoRecord(douyin_id="ZOMBIE_03", account_mark="A3", status="uploading"),
            VideoRecord(douyin_id="ZOMBIE_04", account_mark="A4", status="pending", retry_count=3),
            VideoRecord(douyin_id="ZOMBIE_05", account_mark="A5", status="pending", retry_count=1)
        ]
        for record in test_data:
            VideoDAO.insert_video_if_unique(record)

        # Act
        reverted_count = VideoDAO.revert_zombies()
        
        # Assert returned count only considers processing/downloading and uploading
        self.assertEqual(reverted_count, 3)

        with db_module.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # processing/downloading -> pending, retry_count += 1
            z1 = cursor.execute("SELECT status, retry_count FROM videos WHERE douyin_id='ZOMBIE_01'").fetchone()
            self.assertEqual(z1['status'], 'pending')
            self.assertEqual(z1['retry_count'], 1)
            
            z2 = cursor.execute("SELECT status, retry_count FROM videos WHERE douyin_id='ZOMBIE_02'").fetchone()
            self.assertEqual(z2['status'], 'pending')
            self.assertEqual(z2['retry_count'], 1)

            # uploading -> downloaded, retry_count += 1
            z3 = cursor.execute("SELECT status, retry_count FROM videos WHERE douyin_id='ZOMBIE_03'").fetchone()
            self.assertEqual(z3['status'], 'downloaded')
            self.assertEqual(z3['retry_count'], 1)
            
            # pending with retry_count >= 3 -> give_up_fatal
            z4 = cursor.execute("SELECT status, retry_count FROM videos WHERE douyin_id='ZOMBIE_04'").fetchone()
            self.assertEqual(z4['status'], 'give_up_fatal')
            self.assertEqual(z4['retry_count'], 3)

            # verify normal pending unaffected
            z5 = cursor.execute("SELECT status, retry_count FROM videos WHERE douyin_id='ZOMBIE_05'").fetchone()
            self.assertEqual(z5['status'], 'pending')
            self.assertEqual(z5['retry_count'], 1)

    def test_get_uploadable_videos_respects_retry_cap(self):
        now = int(time.time())
        with db_module.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO videos (
                    douyin_id, account_mark, title, description, video_url, cover_url,
                    status, retry_count, local_video_path, created_at, updated_at
                ) VALUES (?, 'A', 't', '', '', '', 'failed', 5, '/x/a.mp4', ?, ?)
                """,
                ("UP_CAP_1", now, now),
            )
            conn.commit()
        self.assertEqual(len(VideoDAO.get_uploadable_videos(limit=5)), 0)
        rows = VideoDAO.get_uploadable_videos(limit=5, ignore_retry_cap=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].douyin_id, "UP_CAP_1")

    def test_prepare_for_force_manual_retry(self):
        now = int(time.time())
        with db_module.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO videos (
                    douyin_id, account_mark, title, description, video_url, cover_url,
                    status, retry_count, local_video_path, local_cover_path, created_at, updated_at
                ) VALUES
                ('F1', 'A', '', '', '', '', 'give_up', 3, NULL, NULL, ?, ?),
                ('F2', 'A', '', '', '', '', 'give_up_fatal', 3, '/p/v.mp4', NULL, ?, ?),
                ('F3', 'A', '', '', '', '', 'failed', 9, '/p/w.mp4', NULL, ?, ?),
                ('F4', 'A', '', '', '', '', 'failed', 2, NULL, NULL, ?, ?)
                """,
                (now, now, now, now, now, now, now, now),
            )
            conn.commit()

        n = VideoDAO.prepare_for_force_manual_retry()
        self.assertGreaterEqual(n, 4)

        with db_module.db.get_connection() as conn:
            r1 = conn.execute("SELECT status, retry_count, local_video_path FROM videos WHERE douyin_id='F1'").fetchone()
            self.assertEqual(r1["status"], "pending")
            self.assertEqual(r1["retry_count"], 0)
            self.assertIsNone(r1["local_video_path"])

            r2 = conn.execute("SELECT status, retry_count FROM videos WHERE douyin_id='F2'").fetchone()
            self.assertEqual(r2["status"], "downloaded")
            self.assertEqual(r2["retry_count"], 0)

            r3 = conn.execute("SELECT status, retry_count FROM videos WHERE douyin_id='F3'").fetchone()
            self.assertEqual(r3["status"], "downloaded")
            self.assertEqual(r3["retry_count"], 0)

            r4 = conn.execute("SELECT status, retry_count FROM videos WHERE douyin_id='F4'").fetchone()
            self.assertEqual(r4["status"], "pending")
            self.assertEqual(r4["retry_count"], 0)

if __name__ == '__main__':
    unittest.main()
