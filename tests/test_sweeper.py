"""
tests/test_sweeper.py

Unit tests for modules/sweeper.DiskSweeper.

Covers:
- Old media files are deleted
- New media files are kept
- Non-target extensions are never deleted
- check_preflight_space() returns False when free disk < 2GB
- check_preflight_space() returns True when free disk >= 2GB
- PermissionError during deletion does not halt the sweep loop
"""
import os
import time
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest

import modules.sweeper as sweeper_module
from modules.sweeper import DiskSweeper


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sweeper(tmp_path, monkeypatch):
    """Return a DiskSweeper with DOWNLOAD_DIR redirected to a temp folder."""
    monkeypatch.setattr(sweeper_module, "DOWNLOAD_DIR", tmp_path)
    return DiskSweeper()


def make_file(path: Path, age_days: float, content: bytes = b"fake_media") -> Path:
    """Create a file and backdate its mtime to simulate age."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    mtime = time.time() - age_days * 86400
    os.utime(path, (mtime, mtime))
    return path


# ---------------------------------------------------------------------------
# purge_stale_media() — deletion behaviour
# ---------------------------------------------------------------------------

class TestPurgeStaleMedia:
    def test_old_mp4_is_deleted(self, sweeper, tmp_path):
        """Files older than max_age_days must be unlinked."""
        f = make_file(tmp_path / "old.mp4", age_days=10)
        sweeper.purge_stale_media(max_age_days=7)
        assert not f.exists()

    def test_old_jpg_is_deleted(self, sweeper, tmp_path):
        f = make_file(tmp_path / "old.jpg", age_days=8)
        sweeper.purge_stale_media(max_age_days=7)
        assert not f.exists()

    def test_old_webp_is_deleted(self, sweeper, tmp_path):
        f = make_file(tmp_path / "old.webp", age_days=14)
        sweeper.purge_stale_media(max_age_days=7)
        assert not f.exists()

    def test_new_mp4_is_kept(self, sweeper, tmp_path):
        """Files newer than max_age_days must NOT be touched."""
        f = make_file(tmp_path / "new.mp4", age_days=2)
        sweeper.purge_stale_media(max_age_days=7)
        assert f.exists()

    def test_new_jpg_is_kept(self, sweeper, tmp_path):
        f = make_file(tmp_path / "recent.jpg", age_days=6)
        sweeper.purge_stale_media(max_age_days=7)
        assert f.exists()

    def test_exact_boundary_file_is_kept(self, sweeper, tmp_path):
        """A file aged exactly max_age_days seconds old is NOT deleted (strictly older check)."""
        f = make_file(tmp_path / "boundary.mp4", age_days=7)
        # Set mtime to just after cutoff so it is equal but not older
        mtime = time.time() - 7 * 86400 + 10  # 10 seconds inside the window
        os.utime(f, (mtime, mtime))
        sweeper.purge_stale_media(max_age_days=7)
        assert f.exists()

    def test_non_target_extension_is_never_deleted(self, sweeper, tmp_path):
        """Non-media extensions must survive regardless of age."""
        txt = make_file(tmp_path / "notes.txt", age_days=30)
        log = make_file(tmp_path / "debug.log", age_days=30)
        sweeper.purge_stale_media(max_age_days=7)
        assert txt.exists()
        assert log.exists()

    def test_subdirectory_files_are_swept(self, sweeper, tmp_path):
        """purge_stale_media must recurse into sub-folders."""
        sub = tmp_path / "2024-01-01"
        f = make_file(sub / "deep.mp4", age_days=15)
        sweeper.purge_stale_media(max_age_days=7)
        assert not f.exists()

    def test_mixed_files_partial_deletion(self, sweeper, tmp_path):
        """Only old files from a mixed set should be deleted."""
        old = make_file(tmp_path / "old.mp4", age_days=10)
        new = make_file(tmp_path / "new.mp4", age_days=3)
        sweeper.purge_stale_media(max_age_days=7)
        assert not old.exists()
        assert new.exists()


# ---------------------------------------------------------------------------
# purge_stale_media() — resilience (PermissionError)
# ---------------------------------------------------------------------------

class TestPurgeStaleMediaResilience:
    def test_permission_error_does_not_abort_loop(self, sweeper, tmp_path):
        """A PermissionError on one file must not stop deletion of other files."""
        locked = make_file(tmp_path / "locked.mp4", age_days=10)
        deletable = make_file(tmp_path / "old.jpg", age_days=10)

        original_unlink = Path.unlink
        call_count = {"n": 0}

        def side_effect_unlink(self, missing_ok=False):
            call_count["n"] += 1
            if self.name == "locked.mp4":
                raise PermissionError("File is locked")
            original_unlink(self, missing_ok=missing_ok)

        with patch.object(Path, "unlink", side_effect_unlink):
            sweeper.purge_stale_media(max_age_days=7)

        # The lock raised an error, but sweeper continued and deleted the other file
        assert not deletable.exists()
        assert call_count["n"] >= 2  # Both files were attempted

    def test_os_error_on_stat_skips_file(self, sweeper, tmp_path):
        """An OSError during stat() for mtime must not abort the loop.

        The first file's stat raises OSError → it is skipped (not deleted).
        A second, healthy file should still be processed and deleted.
        """
        f_errored = make_file(tmp_path / "errored.mp4", age_days=10)
        f_ok = make_file(tmp_path / "good.mp4", age_days=10)

        original_stat = Path.stat
        call_count = {"n": 0}

        def side_effect_stat(self_path, **kwargs):
            if self_path.name == "errored.mp4":
                raise OSError("stat failed")
            return original_stat(self_path, **kwargs)

        with patch.object(Path, "stat", side_effect_stat):
            sweeper.purge_stale_media(max_age_days=7)

        # The errored file must be skipped (still exists)
        assert f_errored.exists()
        # The healthy file must have been deleted normally
        assert not f_ok.exists()


# ---------------------------------------------------------------------------
# check_preflight_space()
# ---------------------------------------------------------------------------

class TestCheckPreflightSpace:
    def test_returns_false_when_free_space_below_2gb(self, sweeper):
        mock_usage = (100 * 1024**3, 99 * 1024**3, 1 * 1024**3)  # 1 GB free
        with patch("shutil.disk_usage", return_value=mock_usage):
            result = sweeper.check_preflight_space()
        assert result is False

    def test_returns_true_when_free_space_above_2gb(self, sweeper):
        mock_usage = (100 * 1024**3, 90 * 1024**3, 10 * 1024**3)  # 10 GB free
        with patch("shutil.disk_usage", return_value=mock_usage):
            result = sweeper.check_preflight_space()
        assert result is True

    def test_returns_true_when_free_space_exactly_2gb(self, sweeper):
        """Exactly 2 GB free is acceptable (strict less-than check)."""
        mock_usage = (100 * 1024**3, 98 * 1024**3, 2 * 1024**3)  # exactly 2 GB
        with patch("shutil.disk_usage", return_value=mock_usage):
            result = sweeper.check_preflight_space()
        assert result is True

    def test_returns_true_on_oserror_fallback(self, sweeper):
        """If disk_usage itself raises, the fallback is True (safe to continue)."""
        with patch("shutil.disk_usage", side_effect=OSError("disk error")):
            result = sweeper.check_preflight_space()
        assert result is True
