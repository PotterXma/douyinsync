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

if __name__ == '__main__':
    unittest.main()
