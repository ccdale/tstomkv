from tstomkv import gtk4


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
