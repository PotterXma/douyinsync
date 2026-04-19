import unittest
import sqlite3
from pathlib import Path
import tempfile
import shutil

import modules.database as db_module
from modules.database import DBManager, VideoDAO

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the DB
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_douyinsync.db"
        
        # Override the global DBManager with our test one
        db_module.db = DBManager(self.db_path)
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def test_insert_video_if_unique(self):
        test_video = dict(
            douyin_id="TEST_001",
            account_mark="TEST_ACCOUNT",
            title="Test Title",
            description="Test Desc",
            video_url="http://vid",
            cover_url="http://cover"
        )
        
        # First insertion should succeed
        is_new = VideoDAO.insert_video_if_unique(test_video)
        self.assertTrue(is_new, "First insert should be treated as new.")
        
        # Second insertion should be ignored
        is_new2 = VideoDAO.insert_video_if_unique(test_video)
        self.assertFalse(is_new2, "Duplicate insert should be ignored.")
        
    def test_get_pending_videos(self):
        test_video = dict(
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
        self.assertEqual(pending_list[0]['douyin_id'], "TEST_002")

    def test_update_status(self):
        test_video = dict(
            douyin_id="TEST_003",
            account_mark="TEST_ACCOUNT"
        )
        VideoDAO.insert_video_if_unique(test_video)
        
        VideoDAO.update_status("TEST_003", "downloaded", {"local_video_path": "/fake/path.mp4"})
        
        # Manually query to verify
        with db_module.db.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT status, local_video_path FROM videos WHERE douyin_id = 'TEST_003'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['status'], 'downloaded')
            self.assertEqual(row['local_video_path'], '/fake/path.mp4')

if __name__ == '__main__':
    unittest.main()
