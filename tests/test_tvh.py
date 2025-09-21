from unittest import mock

from tstomkv import tvh

# def test_sendToTvh_success():
#     cfg = {"DEFAULT": {"tvhuser": "user", "tvhpass": "pass", "tvhipaddr": "127.0.0.1"}}
#     with (
#         mock.patch("tstomkv.config.readConfig", return_value=cfg),
#         mock.patch("requests.get") as mget,
#     ):
#         mget.return_value = mock.Mock(status_code=200, json=lambda: {"ok": True})
#         result = tvh.sendToTvh("route", data={"foo": "bar"})
#         assert result == {"ok": True}
#         mget.assert_called_with(
#             "http://127.0.0.1/api/route", params={"foo": "bar"}, auth=("user", "pass")
#         )


# def test_sendToTvh_http_error():
#     cfg = {"DEFAULT": {"tvhuser": "user", "tvhpass": "pass", "tvhipaddr": "127.0.0.1"}}
#     with (
#         mock.patch("tstomkv.config.readConfig", return_value=cfg),
#         mock.patch("requests.get") as mget,
#     ):
#         mget.return_value = mock.Mock(
#             status_code=500, text="fail", json=mock.Mock(side_effect=Exception("fail"))
#         )
#         with mock.patch("tstomkv.errorNotify") as en:
#             tvh.sendToTvh("route")
#             en.assert_called()


def test_sendToTvh_json_decode_error():
    cfg = {"DEFAULT": {"tvhuser": "user", "tvhpass": "pass", "tvhipaddr": "127.0.0.1"}}
    with (
        mock.patch("tstomkv.config.readConfig", return_value=cfg),
        mock.patch("requests.get") as mget,
    ):
        mget.return_value = mock.Mock(
            status_code=200,
            text="bad\x19json",
            json=mock.Mock(side_effect=Exception("fail")),
        )
        with mock.patch("json.loads", return_value={"fixed": True}):
            result = tvh.sendToTvh("route")
            assert result == {"fixed": True}


def test_allRecordings_success():
    with mock.patch(
        "tstomkv.tvh.sendToTvh", return_value={"entries": [1, 2], "total": 2}
    ):
        entries, total = tvh.allRecordings()
        assert entries == [1, 2]
        assert total == 2


# def test_allRecordings_error():
#     with mock.patch("tstomkv.tvh.sendToTvh", side_effect=Exception("fail")):
#         with mock.patch("tstomkv.errorNotify") as en:
#             tvh.allRecordings()
#             en.assert_called()


def test_deleteRecording_calls_send(monkeypatch):
    with mock.patch("tstomkv.tvh.sendToTvh") as send:
        tvh.deleteRecording("uuid")
        send.assert_called_with("dvr/entry/remove", {"uuid": "uuid"})


def test_fileMoved_calls_send(monkeypatch):
    with mock.patch("tstomkv.tvh.sendToTvh") as send:
        tvh.fileMoved("src", "dst")
        send.assert_called_with("dvr/entry/filemoved", {"src": "src", "dst": "dst"})
