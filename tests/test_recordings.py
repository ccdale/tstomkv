import sys
import time
from unittest import mock

import pytest

sys.path.insert(0, sys.path[0] + "/../src")
from tstomkv import recordings


def test_cleanStringStart_removes_prefix():
    assert recordings.cleanStringStart("new:Title") == "Title"
    assert recordings.cleanStringStart("live:Event", remove="live:") == "Event"
    assert recordings.cleanStringStart("other", remove="new:") == "other"
    assert recordings.cleanStringStart(None) is None


def test_cleanTitle():
    assert recordings.cleanTitle("new:live:Show") == "Show"
    assert recordings.cleanTitle("live:new:Show") == "Show"
    assert recordings.cleanTitle("Show") == "Show"


def test_getEpisode():
    assert recordings.getEpisode("Season 2.Episode 5") == ("2", "5")
    assert recordings.getEpisode("Episode 42") == (None, "42")
    assert recordings.getEpisode("Season 3") == ("3", None)
    assert recordings.getEpisode("") == (None, None)
    assert recordings.getEpisode(None) == (None, None)


def test_tidyRecording_basic():
    rec = {
        "channelname": "BBC",
        "disp_description": "desc",
        "duration": 60,
        "episode_disp": "Season 1.Episode 2",
        "disp_extratext": "extra",
        "filename": "/file",
        "filesize": 123,
        "start": 1000,
        "status": "completed",
        "disp_subtitle": " - subtitle",
        "disp_summary": "summary",
        "disp_title": "new:Title",
        "uuid": "abc",
        "start_real": 1000,
        "stop_real": 1060,
        "category": ["cat"],
    }
    with mock.patch("time.ctime", return_value="ctime!"):
        out = recordings.tidyRecording(rec)
        assert out["title"] == "Title"
        assert out["season"] == "1"
        assert out["episode"] == "2"
        assert out["ctimestart"] == "ctime!"
        assert "extra" in out["description"]


# def test_recordedTitles_filters_radio():
#     recs = [
#         {'filename': '/var/lib/tvheadend/radio/abc', 'disp_title': 'Radio', 'disp_subtitle': '', 'disp_description': '', 'episode_disp': '', 'start_real': 0},
#         {'filename': '/var/lib/tvheadend/video/def', 'disp_title': 'Video', 'disp_subtitle': '', 'disp_description': '', 'episode_disp': '', 'start_real': 0},
#     ]
#     with mock.patch('tstomkv.tvh.allRecordings', return_value=(recs, 2)):
#         _, titles = recordings.recordedTitles()
#         assert 'Video' in titles
#         assert 'Radio' not in titles
