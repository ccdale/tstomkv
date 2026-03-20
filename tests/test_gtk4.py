from tstomkv import gtk4, gtk4_transfer


def test_build_title_rows_sorted_and_counts():
    titles = {
        "Zulu Show": [
            {"filename": "/z/2.ts"},
            {"filename": "/z/1.ts"},
        ],
        "": [{"filename": "/untitled.ts"}],
        "Alpha Show": [{"filename": "/a/1.ts"}],
    }

    rows = gtk4._build_title_rows(titles)

    assert [row["display"] for row in rows] == [
        "<No title>",
        "Alpha Show",
        "Zulu Show",
    ]
    assert rows[2]["count"] == 2
    assert rows[2]["recordings"][0]["filename"] == "/z/1.ts"


def test_format_title_details_contains_expected_fields():
    recs = [
        {
            "filename": "/path/example.ts",
            "subtitle": "Episode Name",
            "channelname": "BBC One",
            "season": "2",
            "episode": "5",
        },
        {
            "filename": None,
            "subtitle": None,
            "season": None,
            "episode": None,
        },
    ]

    details = gtk4._format_title_details("Show Title", recs)

    assert "Show Title" in details
    assert "Recordings: 2" in details
    assert "- Episode Name" in details
    assert "channel: BBC One" in details
    assert "episode: S2 E5" in details
    assert "file: <unknown>" in details
    assert "- <No subtitle>" in details


def test_format_filtered_titles_empty_result():
    text = gtk4._format_filtered_titles([], {})

    assert "Transport Stream recordings: 0" in text
    assert "Unique titles: 0" in text
    assert "No recordings returned by filteredTitles()." in text


def test_format_conversion_list_empty():
    text = gtk4._format_conversion_list([])
    assert "No titles selected for conversion." in text


def test_format_conversion_list_single_title():
    selected = [
        {
            "display": "Show Title",
            "count": 2,
            "recordings": [
                {"filename": "/path/rec1.ts"},
                {"filename": "/path/rec2.ts"},
            ],
        }
    ]

    text = gtk4._format_conversion_list(selected)

    assert "Conversion List" in text
    assert "Show Title (2 recordings)" in text
    assert "/path/rec1.ts" in text
    assert "/path/rec2.ts" in text


def test_format_conversion_list_multiple_titles():
    selected = [
        {
            "display": "Show A",
            "count": 1,
            "recordings": [{"filename": "/a/rec.ts"}],
        },
        {
            "display": "Show B",
            "count": 2,
            "recordings": [
                {"filename": "/b/rec1.ts"},
                {"filename": "/b/rec2.ts"},
            ],
        },
    ]

    text = gtk4._format_conversion_list(selected)

    assert "Show A (1 recording)" in text
    assert "Show B (2 recordings)" in text
    assert "/a/rec.ts" in text
    assert "/b/rec1.ts" in text
    assert "/b/rec2.ts" in text


def test_main_returns_error_when_gtk_unavailable(monkeypatch, capsys):
    monkeypatch.setattr(gtk4, "Gtk", None)

    result = gtk4.main()

    out, _ = capsys.readouterr()
    assert result == 1
    assert "GTK4 unavailable" in out


def test_calculate_progress_no_file():
    progress, bytes_tx, rate = gtk4._calculate_progress(
        1000, "/nonexistent/file.ts", 1.0
    )
    assert progress == 0.0
    assert bytes_tx == 0
    assert rate == 0.0


def test_calculate_progress_partial(tmp_path):
    src_size = 1000
    dst_file = tmp_path / "test.ts"
    dst_file.write_bytes(b"x" * 250)

    progress, bytes_tx, rate = gtk4._calculate_progress(
        src_size, str(dst_file), elapsed_time=1.0
    )

    assert progress == 0.25
    assert bytes_tx == 250
    assert rate == 250.0


def test_calculate_progress_complete(tmp_path):
    src_size = 1000
    dst_file = tmp_path / "test.ts"
    dst_file.write_bytes(b"x" * 1000)

    progress, bytes_tx, rate = gtk4._calculate_progress(
        src_size, str(dst_file), elapsed_time=2.0
    )

    assert progress == 1.0
    assert bytes_tx == 1000
    assert rate == 500.0


def test_format_transfer_status():
    status = gtk4._format_transfer_status(
        "test.ts",
        src_size=1024 * 1024,
        dst_size=512 * 1024,
        elapsed=10.0,
        rate=51200.0,
    )

    assert "test.ts" in status
    assert "512.00 KB" in status
    assert "1.00 MB" in status
    assert "50.0%" in status
    assert "50.00 KB/s" in status


def test_format_elapsed_mmss():
    assert gtk4._format_elapsed_mmss(0) == "00:00"
    assert gtk4._format_elapsed_mmss(65) == "01:05"
    assert gtk4._format_elapsed_mmss(600) == "10:00"
    assert gtk4._format_elapsed_mmss(-3) == "00:00"


def test_collect_all_files_from_selected_titles():
    """Test that all files are collected from all selected titles."""
    selected_titles = [
        {
            "display": "Title A",
            "recordings": [
                {"filename": "/media/a1.ts"},
                {"filename": "/media/a2.ts"},
            ],
        },
        {
            "display": "Title B",
            "recordings": [
                {"filename": "/media/b1.ts"},
            ],
        },
    ]

    # Simulate the logic from _on_copy_files_clicked
    file_pairs = []
    for title_row in selected_titles:
        recordings = title_row.get("recordings", [])
        for rec in recordings:
            src_file = rec.get("filename")
            if src_file:
                dst_file = f"/tmp/{src_file.split('/')[-1]}"
                file_pairs.append((src_file, dst_file))

    assert len(file_pairs) == 3
    assert file_pairs[0][0] == "/media/a1.ts"
    assert file_pairs[1][0] == "/media/a2.ts"
    assert file_pairs[2][0] == "/media/b1.ts"


def test_reconcile_existing_destination_skip_when_hash_matches(tmp_path, monkeypatch):
    dst = tmp_path / "existing.ts"
    dst.write_bytes(b"same-content")
    dst_sha = gtk4_transfer._local_file_sha256(dst)

    monkeypatch.setattr(gtk4_transfer, "_remote_file_sha256", lambda _src: dst_sha)

    skip_copy, status = gtk4_transfer._reconcile_existing_destination(
        "/remote/source.ts", str(dst)
    )

    assert skip_copy is True
    assert "Skipping" in status
    assert dst.exists()


def test_reconcile_existing_destination_replace_when_hash_differs(
    tmp_path, monkeypatch
):
    dst = tmp_path / "existing.ts"
    dst.write_bytes(b"old-content")

    monkeypatch.setattr(
        gtk4_transfer,
        "_remote_file_sha256",
        lambda _src: "0" * 64,
    )

    skip_copy, status = gtk4_transfer._reconcile_existing_destination(
        "/remote/source.ts", str(dst)
    )

    assert skip_copy is False
    assert "Replacing" in status
    assert not dst.exists()


def test_parse_stats_content_extracts_values():
    raw = """frame=10
out_time_ms=2500000
speed=1.25x
progress=continue
"""
    stats = gtk4_transfer._parse_stats_content(raw)
    assert stats["frame"] == "10"
    assert stats["out_time_ms"] == "2500000"
    assert stats["speed"] == "1.25x"
    assert stats["progress"] == "continue"


def test_stats_elapsed_seconds_uses_fallback_when_invalid():
    stats = {"out_time_ms": "N/A"}
    assert gtk4_transfer._stats_elapsed_seconds(stats, fallback=3.5) == 3.5


def test_conversion_progress_fraction_bounds():
    assert gtk4_transfer._conversion_progress_fraction(5, 10) == 0.5
    assert gtk4_transfer._conversion_progress_fraction(15, 10) == 1.0
    assert gtk4_transfer._conversion_progress_fraction(-2, 10) == 0.0
    assert gtk4_transfer._conversion_progress_fraction(2, 0) == 0.0


def test_format_conversion_status_with_duration():
    status = gtk4_transfer._format_conversion_status(
        "video.ts", elapsed_seconds=30, duration_seconds=120, speed="0.9x"
    )
    assert "Converting video.ts" in status
    assert "25.0%" in status
    assert "00:30/02:00" in status
    assert "0.9x" in status


def test_publish_converted_output_success(monkeypatch, tmp_path):
    local_mkv = tmp_path / "episode.mkv"
    local_mkv.write_bytes(b"mkv")

    calls = {"moved": None, "commands": []}

    monkeypatch.setattr(gtk4_transfer, "sendFile", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(gtk4_transfer, "_local_file_sha256", lambda _p: "a" * 64)
    monkeypatch.setattr(gtk4_transfer, "_remote_file_sha256", lambda _p: "a" * 64)

    def _fake_moved(src, dst):
        calls["moved"] = (src, dst)

    monkeypatch.setattr(gtk4_transfer, "fileMoved", _fake_moved)

    def _fake_remote_command(cmd):
        calls["commands"].append(cmd)
        return "__deleted__"

    monkeypatch.setattr(
        gtk4_transfer,
        "remoteCommand",
        _fake_remote_command,
    )

    ok, msg = gtk4_transfer._publish_converted_output(
        "/var/lib/tvheadend/rec/episode.ts", str(local_mkv)
    )

    assert ok is True
    assert "Published" in msg
    assert calls["moved"] == (
        "/var/lib/tvheadend/rec/episode.ts",
        "/var/lib/tvheadend/rec/episode.mkv",
    )
    assert (
        calls["commands"][-1]
        == 'rm -f "/var/lib/tvheadend/rec/episode.ts" && echo __deleted__'
    )


def test_publish_converted_output_stops_on_upload_failure(monkeypatch, tmp_path):
    local_mkv = tmp_path / "episode.mkv"
    local_mkv.write_bytes(b"mkv")

    called = {"moved": False, "deleted": False}

    monkeypatch.setattr(gtk4_transfer, "sendFile", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        gtk4_transfer,
        "fileMoved",
        lambda *_args, **_kwargs: called.update({"moved": True}),
    )
    monkeypatch.setattr(
        gtk4_transfer,
        "remoteCommand",
        lambda *_args, **_kwargs: called.update({"deleted": True}) or "",
    )

    ok, msg = gtk4_transfer._publish_converted_output(
        "/var/lib/tvheadend/rec/episode.ts", str(local_mkv)
    )

    assert ok is False
    assert "Failed to upload" in msg
    assert called["moved"] is False
    assert called["deleted"] is False


def test_publish_converted_output_fails_on_checksum_mismatch(monkeypatch, tmp_path):
    local_mkv = tmp_path / "episode.mkv"
    local_mkv.write_bytes(b"mkv")

    called = {"moved": False, "commands": []}

    monkeypatch.setattr(gtk4_transfer, "sendFile", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(gtk4_transfer, "_local_file_sha256", lambda _p: "a" * 64)
    monkeypatch.setattr(gtk4_transfer, "_remote_file_sha256", lambda _p: "b" * 64)
    monkeypatch.setattr(
        gtk4_transfer,
        "fileMoved",
        lambda *_args, **_kwargs: called.update({"moved": True}),
    )
    monkeypatch.setattr(
        gtk4_transfer,
        "remoteCommand",
        lambda cmd: called["commands"].append(cmd) or "",
    )

    ok, msg = gtk4_transfer._publish_converted_output(
        "/var/lib/tvheadend/rec/episode.ts", str(local_mkv)
    )

    assert ok is False
    assert "checksum mismatch" in msg
    assert called["moved"] is False
    assert called["commands"] == ['rm -f "/var/lib/tvheadend/rec/episode.mkv"']


def test_publish_converted_output_reports_stage_progress(monkeypatch, tmp_path):
    local_mkv = tmp_path / "episode.mkv"
    local_mkv.write_bytes(b"mkv")

    stages = []

    monkeypatch.setattr(gtk4_transfer, "sendFile", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(gtk4_transfer, "_local_file_sha256", lambda _p: "a" * 64)
    monkeypatch.setattr(gtk4_transfer, "_remote_file_sha256", lambda _p: "a" * 64)
    monkeypatch.setattr(gtk4_transfer, "fileMoved", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        gtk4_transfer, "remoteCommand", lambda *_args, **_kwargs: "__deleted__"
    )

    ok, _msg = gtk4_transfer._publish_converted_output(
        "/var/lib/tvheadend/rec/episode.ts",
        str(local_mkv),
        progress_callback=lambda status, fraction: stages.append((status, fraction)),
    )

    assert ok is True
    fractions = [fraction for _status, fraction in stages]
    assert fractions[0] == 0.20
    assert 0.45 in fractions
    assert 0.70 in fractions
    assert 0.90 in fractions
    assert fractions[-1] == 1.0


def test_desktop_notify_falls_back_to_notify_send(monkeypatch):
    class _Result:
        returncode = 0

    calls = []

    monkeypatch.setattr(gtk4_transfer, "Gtk", None)
    monkeypatch.setattr(
        gtk4_transfer.subprocess,
        "run",
        lambda cmd, capture_output, check: calls.append(cmd) or _Result(),
    )

    ok = gtk4_transfer._desktop_notify("done", "workflow complete")

    assert ok is True
    assert calls[0][0] == "notify-send"


def test_desktop_notify_returns_false_when_notify_send_unavailable(monkeypatch):
    monkeypatch.setattr(gtk4_transfer, "Gtk", None)

    def _raise(*_args, **_kwargs):
        raise OSError("notify-send missing")

    monkeypatch.setattr(gtk4_transfer.subprocess, "run", _raise)

    ok = gtk4_transfer._desktop_notify("done", "workflow complete")

    assert ok is False
