"""Pure helpers for classic videolib (`modules/dashboard.py`)."""

from modules.dashboard import (
    _format_last_error_summary,
    _format_library_upload_progress,
    _format_youtube_id_cell,
)


def test_last_error_summary_truncates():
    raw = "e" * 100
    out = _format_last_error_summary(raw, max_len=20)
    assert len(out) == 20
    assert out.endswith("…")


def test_last_error_summary_newlines_flattened():
    assert _format_last_error_summary("a\nb") == "a b"


def test_library_upload_progress():
    assert _format_library_upload_progress("uploading", 50, 100) == "50%"
    assert _format_library_upload_progress("pending", 0, None) == "—"
    assert _format_library_upload_progress("uploading", 0, None) == "…"


def test_youtube_id_cell():
    assert _format_youtube_id_cell(None) == "—"
    assert _format_youtube_id_cell("") == "—"
    assert _format_youtube_id_cell("abcXYZ09-_") == "abcXYZ09-_"
