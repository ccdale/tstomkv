import os
from unittest import mock

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tstomkv import files  # noqa: E402
from tstomkv.config import expandPath, writeConfig  # noqa: E402


def test_getOutputFileName_increments_and_formats(monkeypatch):
    cfg = {
        "youtube": {
            "filenumber": "5",
            "videodir": "videos",
            "playlistdir": "playlists",
            "iplayerdir": "iplayer",
        },
        "mediaserver": {"homedir": "/home/user/"},
    }
    monkeypatch.setattr(os.path, "expanduser", lambda x: x.replace("~", "/home/user"))
    out = files.getOutputFileName(cfg, vtype="v")
    assert out == "/home/user/videos/05"


def test_getOutputFileName_rollover(monkeypatch):
    cfg = {
        "youtube": {
            "filenumber": "99",
            "videodir": "videos",
            "playlistdir": "playlists",
            "iplayerdir": "iplayer",
        }
    }
    monkeypatch.setattr(os.path, "expanduser", lambda x: x.replace("~", "/home/user")),
    with (
        # mock.patch("tstomkv.config.expandPath", return_value="/home/user/videos"),
        mock.patch("tstomkv.config.writeConfig"),
    ):
        out = files.getOutputFileName(cfg, vtype="v")
        assert out.endswith("/99")
        assert cfg["youtube"]["filenumber"] == "0"


# def test_sendFileTo_calls_connection(monkeypatch):
#     cfg = {
#         "mediaserver": {"host": "host", "user": "user", "keyfn": "id_rsa"},
#         "youtube": {
#             "filenumber": "1",
#             "videodir": "videos",
#             "playlistdir": "playlists",
#             "iplayerdir": "iplayer",
#         },
#     }
#     with (
#         mock.patch("tstomkv.config.readConfig", return_value=cfg),
#         mock.patch("tstomkv.config.expandPath", return_value="/home/user/.ssh/id_rsa"),
#         mock.patch("tstomkv.files.getOutputFileName", return_value="/remote/file"),
#         mock.patch("fabric.Connection") as mconn,
#     ):
#         files.sendFileTo("localfile", vtype="v")
#         mconn.assert_called_with(
#             host="host",
#             user="user",
#             connect_kwargs={"key_filename": "/home/user/.ssh/id_rsa"},
#         )
#         mconn().__enter__().put.assert_called_with("localfile", "/remote/file")


def test_homeDir_returns_home(monkeypatch):
    monkeypatch.setenv("HOME", "/myhome")
    assert files.homeDir() == "/myhome"


def test_dirFileList_filters(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.log").write_text("y")
    (tmp_path / "c.txt").write_text("z")
    files_list = files.dirFileList(str(tmp_path), filterext=".log")
    assert "a.txt" in files_list and "c.txt" in files_list and "b.log" not in files_list


def test_dirFileList_none(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    files_list = files.dirFileList(str(tmp_path))
    assert "a.txt" in files_list


def test_remoteFinalFileName_returns_original_if_not_exists(monkeypatch):
    cfg = {
        "mediaserver": {"host": "host", "user": "user", "keyfn": "id_rsa"},
        "DEFAULT": {"transcodedir": "/transcodedir"},
    }

    # Simulate file does not exist on remote
    class DummyResult:
        exited = 1

    dummy_conn = mock.MagicMock()
    dummy_conn.run.return_value = DummyResult()
    dummy_context = mock.MagicMock()
    dummy_context.__enter__.return_value = dummy_conn
    dummy_context.__exit__.return_value = False

    with (
        mock.patch("tstomkv.config.readConfig", return_value=cfg),
        # mock.patch(
        #     "tstomkv.config.expandPath", return_value="/home/user/.config/tstomkv.cfg"
        # ),
        mock.patch("fabric.Connection", return_value=dummy_context),
    ):
        result = files.remoteFinalFileName("/some/path/file.ts")
        assert result == "/some/path/file.ts"


# def test_remoteFinalFileName_adds_suffix_if_exists(monkeypatch):
#     cfg = {
#         "mediaserver": {"host": "host", "user": "user", "keyfn": "id_rsa"},
#         "DEFAULT": {"transcodedir": "/transcodedir"},
#     }
#
#     # Simulate file exists on remote for first check, not for second
#     class DummyResultExists:
#         exited = 0
#
#     class DummyResultNotExists:
#         exited = 1
#
#     dummy_conn = mock.MagicMock()
#     dummy_conn.run.side_effect = [DummyResultExists(), DummyResultNotExists()]
#     dummy_context = mock.MagicMock()
#     dummy_context.__enter__.return_value = dummy_conn
#     dummy_context.__exit__.return_value = False
#
#     with (
#         mock.patch("tstomkv.config.readConfig", return_value=cfg),
#         # mock.patch("tstomkv.config.expandPath", return_value="/home/user/.ssh/id_rsa"),
#         mock.patch("fabric.Connection", return_value=dummy_context),
#     ):
#         result = files.remoteFinalFileName("/some/path/file.ts")
#         assert result == "/some/path/file-1.ts"
#
#
# def test_remoteFinalFileName_multiple_suffix(monkeypatch):
#     cfg = {
#         "mediaserver": {"host": "host", "user": "user", "keyfn": "id_rsa"},
#         "DEFAULT": {"transcodedir": "/transcodedir"},
#     }
#
#     # Simulate file exists for first two checks, not for third
#     class DummyResultExists:
#         exited = 0
#
#     class DummyResultNotExists:
#         exited = 1
#
#     dummy_conn = mock.MagicMock()
#     dummy_conn.run.side_effect = [
#         DummyResultExists(),  # file.ts exists
#         DummyResultExists(),  # file-1.ts exists
#         DummyResultNotExists(),  # file-2.ts does not exist
#     ]
#     dummy_context = mock.MagicMock()
#     dummy_context.__enter__.return_value = dummy_conn
#     dummy_context.__exit__.return_value = False
#
#     with (
#         mock.patch("tstomkv.config.readConfig", return_value=cfg),
#         # mock.patch("tstomkv.config.expandPath", return_value="/home/user/.ssh/id_rsa"),
#         mock.patch("fabric.Connection", return_value=dummy_context),
#     ):
#         result = files.remoteFinalFileName("/some/path/file.ts")
#         assert result == "/some/path/file-2.ts"
#
