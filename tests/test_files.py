from unittest import mock

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tstomkv import files  # noqa: E402

# def test_getOutputFileName_increments_and_formats(monkeypatch):
#     cfg = {
#         "youtube": {
#             "filenumber": "5",
#             "videodir": "videos",
#             "playlistdir": "playlists",
#             "iplayerdir": "iplayer",
#         }
#     }
#     with (
#         mock.patch(
#             "tstomkv.config.expandPath",
#             side_effect=lambda p: "/home/chris/" + p.split("~/")[1],
#         ),
#         mock.patch("tstomkv.config.writeConfig") as wcfg,
#     ):
#         out = files.getOutputFileName(cfg, vtype="v")
#         assert out == "/home/chris/videos/05"
#         assert cfg["youtube"]["filenumber"] == "6"
#         wcfg.assert_called_once()


def test_getOutputFileName_rollover(monkeypatch):
    cfg = {
        "youtube": {
            "filenumber": "99",
            "videodir": "videos",
            "playlistdir": "playlists",
            "iplayerdir": "iplayer",
        }
    }
    with (
        mock.patch("tstomkv.config.expandPath", return_value="/home/chris/videos"),
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
#


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
