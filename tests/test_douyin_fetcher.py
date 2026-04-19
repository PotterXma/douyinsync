import unittest
from modules.douyin_fetcher import DouyinFetcher

class TestDouyinFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = DouyinFetcher()
        
    def test_extract_sec_user_id_success(self):
        url = "https://www.douyin.com/user/MS4wLjABAAAADCvhGc9nim1IjpbUh2fJShMcvh9wmHDpGIF0RmKMLzFybrvoatS5CmMVRdLOOcG7"
        sec_user_id = self.fetcher._extract_sec_user_id(url)
        self.assertEqual(sec_user_id, "MS4wLjABAAAADCvhGc9nim1IjpbUh2fJShMcvh9wmHDpGIF0RmKMLzFybrvoatS5CmMVRdLOOcG7")
        
    def test_extract_sec_user_id_fail(self):
        # A malformed or different URL
        url = "https://www.douyin.com/notuser/MS4wL"
        sec_user_id = self.fetcher._extract_sec_user_id(url)
        self.assertEqual(sec_user_id, "")
        
    def test_parse_video_list_valid_payload(self):
        mock_payload = {
            "aweme_list": [
                {
                    "aweme_id": "123456",
                    "desc": "Test video 1",
                    "video": {
                        "bit_rate": [
                            {"bit_rate": 1000, "play_addr": {"url_list": ["http://vid.low"]}},
                            {"bit_rate": 2000, "play_addr": {"url_list": ["http://vid.high"]}}
                        ],
                        "cover": {"url_list": ["http://cover.jpg"]}
                    }
                },
                {
                    "aweme_id": "789012",
                    "aweme_type": 68, # Image post, should be filtered
                    "desc": "Image post"
                }
            ]
        }
        
        results = self.fetcher._parse_video_list(mock_payload)
        
        # Test 1: Only the video post should be parsed (image post filtered)
        self.assertEqual(len(results), 1)
        
        # Test 2: Verify fields
        video_rec = results[0]
        self.assertEqual(video_rec["douyin_id"], "123456")
        self.assertEqual(video_rec["title"], "Test video 1")
        # Test 3: The highest bitrate URL should have been selected
        self.assertEqual(video_rec["video_url"], "http://vid.high")
        self.assertEqual(video_rec["cover_url"], "http://cover.jpg")

if __name__ == '__main__':
    unittest.main()
