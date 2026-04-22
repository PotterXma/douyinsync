"""
tests/test_douyin_api.py

Unit tests for modules/douyin_fetcher.py.
Validates that DouyinFetcher._parse_video_list returns strongly-typed
VideoRecord instances and that sec_user_id extraction works correctly.
All tests are synchronous and use unittest (matching project conventions).
"""
import unittest
from modules.douyin_fetcher import DouyinFetcher
from utils.models import VideoRecord


class TestDouyinFetcher(unittest.TestCase):
    def setUp(self) -> None:
        self.fetcher = DouyinFetcher()

    # ──────────────────────────────────────────────
    # sec_user_id extraction
    # ──────────────────────────────────────────────

    def test_extract_sec_user_id_success(self) -> None:
        """Valid profile URL must yield the sec_user_id path segment."""
        url = (
            "https://www.douyin.com/user/"
            "MS4wLjABAAAADCvhGc9nim1IjpbUh2fJShMcvh9wmHDpGIF0RmKMLzFybrvoatS5CmMVRdLOOcG7"
        )
        result = self.fetcher._extract_sec_user_id(url)
        self.assertEqual(
            result,
            "MS4wLjABAAAADCvhGc9nim1IjpbUh2fJShMcvh9wmHDpGIF0RmKMLzFybrvoatS5CmMVRdLOOcG7",
        )

    def test_extract_sec_user_id_fail(self) -> None:
        """Malformed URL (missing /user/ segment) must return empty string."""
        url = "https://www.douyin.com/notuser/MS4wL"
        result = self.fetcher._extract_sec_user_id(url)
        self.assertEqual(result, "")

    def test_extract_sec_user_id_empty_url(self) -> None:
        """Empty string URL must return empty string without raising."""
        result = self.fetcher._extract_sec_user_id("")
        self.assertEqual(result, "")

    # ──────────────────────────────────────────────
    # _parse_video_list — return type guardrails
    # ──────────────────────────────────────────────

    def test_parse_video_list_returns_video_records(self) -> None:
        """_parse_video_list MUST return a list of VideoRecord (not dict)."""
        payload = {
            "aweme_list": [
                {
                    "aweme_id": "123456",
                    "desc": "Test video 1",
                    "video": {
                        "bit_rate": [
                            {"bit_rate": 1000, "play_addr": {"url_list": ["http://vid.low"]}},
                            {"bit_rate": 2000, "play_addr": {"url_list": ["http://vid.high"]}},
                        ],
                        "cover": {"url_list": ["http://cover.jpg"]},
                    },
                }
            ]
        }
        results = self.fetcher._parse_video_list(payload)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], VideoRecord, "Must be a VideoRecord, not a dict")

    def test_parse_video_list_highest_bitrate_selected(self) -> None:
        """Parser selects the highest bitrate URL from the bit_rate array."""
        payload = {
            "aweme_list": [
                {
                    "aweme_id": "123456",
                    "desc": "Test video 1",
                    "video": {
                        "bit_rate": [
                            {"bit_rate": 1000, "play_addr": {"url_list": ["http://vid.low"]}},
                            {"bit_rate": 2000, "play_addr": {"url_list": ["http://vid.high"]}},
                        ],
                        "cover": {"url_list": ["http://cover.jpg"]},
                    },
                }
            ]
        }
        results = self.fetcher._parse_video_list(payload)
        self.assertEqual(results[0].douyin_id, "123456")
        self.assertEqual(results[0].title, "Test video 1")
        self.assertEqual(results[0].video_url, "http://vid.high")
        self.assertEqual(results[0].cover_url, "http://cover.jpg")

    def test_parse_video_list_image_posts_filtered(self) -> None:
        """Image posts (aweme_type=68 or images != None) must be silently discarded."""
        payload = {
            "aweme_list": [
                {
                    "aweme_id": "AAA",
                    "aweme_type": 68,
                    "desc": "Image post — must be filtered",
                },
                {
                    "aweme_id": "BBB",
                    "images": ["http://img1.jpg"],
                    "desc": "Image-with-images-field — must be filtered",
                    "video": {"bit_rate": [], "cover": {"url_list": []}},
                },
            ]
        }
        results = self.fetcher._parse_video_list(payload)
        self.assertEqual(len(results), 0, "Image posts must be filtered out completely")

    def test_parse_video_list_empty_aweme_list(self) -> None:
        """Empty aweme_list must return an empty list without raising."""
        payload = {"aweme_list": []}
        results = self.fetcher._parse_video_list(payload)
        self.assertEqual(results, [])

    def test_parse_video_list_invalid_root(self) -> None:
        """Non-dict root must return an empty list without raising."""
        results = self.fetcher._parse_video_list([])  # type: ignore[arg-type]
        self.assertEqual(results, [])

    def test_parse_video_list_fallback_play_addr(self) -> None:
        """If bit_rate is absent, falls back to direct play_addr URL list."""
        payload = {
            "aweme_list": [
                {
                    "aweme_id": "FALLBACK_001",
                    "desc": "Fallback test",
                    "video": {
                        "play_addr": {"url_list": ["http://fallback.mp4"]},
                        "cover": {"url_list": []},
                    },
                }
            ]
        }
        results = self.fetcher._parse_video_list(payload)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].video_url, "http://fallback.mp4")

    def test_parse_video_list_title_truncated_to_300(self) -> None:
        """Titles exceeding 300 characters must be truncated to prevent DB overflow."""
        long_title = "A" * 400
        payload = {
            "aweme_list": [
                {
                    "aweme_id": "TRUNC_001",
                    "desc": long_title,
                    "video": {
                        "play_addr": {"url_list": ["http://vid.mp4"]},
                        "cover": {"url_list": []},
                    },
                }
            ]
        }
        results = self.fetcher._parse_video_list(payload)
        self.assertEqual(len(results[0].title), 300)

    def test_parse_video_list_missing_video_key_skipped(self) -> None:
        """Items with missing mandatory video keys must be skipped gracefully."""
        payload = {
            "aweme_list": [
                {
                    # aweme_id intentionally missing to trigger KeyError
                    "desc": "bad item",
                    "video": {"bit_rate": [], "cover": {"url_list": []}},
                }
            ]
        }
        # Must not raise; must return empty list
        results = self.fetcher._parse_video_list(payload)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
