"""CSV export helper for classic videolib (`modules.dashboard.write_videolib_csv_file`)."""

from modules.dashboard import write_videolib_csv_file


def test_write_videolib_csv_full_error_not_truncated(tmp_path):
    p = tmp_path / "videolib.csv"
    rows = [
        (
            "7633726685170371882",
            "failed",
            "Acc",
            1,
            "Hello",
            r"D:\dl\video.mp4",
            1700000000,
            10,
            100,
            "Upload failed: 401 Unauthorized — full detail here",
            None,
        ),
    ]
    n = write_videolib_csv_file(str(p), rows)
    assert n == 1
    raw = p.read_text(encoding="utf-8-sig")
    assert "401 Unauthorized" in raw
    assert "full detail here" in raw


def test_write_videolib_csv_skips_short_rows(tmp_path):
    p = tmp_path / "bad.csv"
    n = write_videolib_csv_file(str(p), [("only", "two")])
    assert n == 0
    text = p.read_text(encoding="utf-8-sig")
    assert "only" not in text.splitlines()[1:]  # header only, no bad partial row
