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


def test_main_returns_error_when_gtk_unavailable(monkeypatch, capsys):
    monkeypatch.setattr(gtk4, "Gtk", None)

    result = gtk4.main()

    out, _ = capsys.readouterr()
    assert result == 1
    assert "GTK4 unavailable" in out
