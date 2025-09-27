import types  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402

import pytest  # noqa: E402

import tstomkv.ffmpeg as ffmpeg


def test_convert_ts_to_mkv_valid(capsys):
    with mock.patch("subprocess.run") as mrun:
        mrun.return_value = types.SimpleNamespace(
            returncode=0, raise_for_status=lambda: None, stdout="ok", stderr=""
        )
        ffmpeg.convert_ts_to_mkv("input.ts", "output.mkv", "stats.txt")
        out = capsys.readouterr().out
        assert "Transcoding input.ts to output.mkv" in out
        mrun.assert_called()
        args = mrun.call_args[0][0]
        assert "-progress" in args and "stats.txt" in args


def test_convert_ts_to_mkv_invalid_input():
    with mock.patch(
        "tstomkv.errorRaise",
        side_effect=lambda exci, e, fname=None: (_ for _ in ()).throw(e),
    ):
        with pytest.raises(ValueError):
            ffmpeg.convert_ts_to_mkv("input.mp4", "output.mkv", "stats.txt")


def test_convert_ts_to_mkv_invalid_output():
    with mock.patch(
        "tstomkv.errorRaise",
        side_effect=lambda exci, e, fname=None: (_ for _ in ()).throw(e),
    ):
        with pytest.raises(ValueError):
            ffmpeg.convert_ts_to_mkv("input.ts", "output.mp4", "stats.txt")


def test_removeFileIfExists_removes(tmp_path):
    f = tmp_path / "toremove.txt"
    f.write_text("data")
    assert f.exists()
    assert ffmpeg.removeFileIfExists(str(f)) is True
    assert not f.exists()


def test_removeFileIfExists_reportOnly(tmp_path):
    f = tmp_path / "toremove.txt"
    f.write_text("data")
    assert ffmpeg.removeFileIfExists(str(f), reportOnly=True) is True
    assert f.exists()


def test_removeFileIfExists_not_exists(tmp_path):
    f = tmp_path / "notfound.txt"
    assert ffmpeg.removeFileIfExists(str(f)) is False


def test_fileInfo_success(tmp_path):
    fakefile = tmp_path / "video.ts"
    fakefile.write_text("dummy")
    with mock.patch("subprocess.run") as mrun:
        mrun.return_value = types.SimpleNamespace(
            returncode=0, stdout=b'{"streams": []}'
        )
        info = ffmpeg.fileInfo(str(fakefile))
        assert isinstance(info, dict)
        assert "streams" in info


def test_fileInfo_fail(tmp_path):
    fakefile = tmp_path / "video.ts"
    fakefile.write_text("dummy")
    with mock.patch("subprocess.run") as mrun:
        mrun.return_value = types.SimpleNamespace(returncode=1, stdout=b"")
        assert ffmpeg.fileInfo(str(fakefile)) is None


def test_fileInfo_no_file(tmp_path):
    fakefile = tmp_path / "nofile.ts"
    assert ffmpeg.fileInfo(str(fakefile)) is None


def test_takeSnapshot_success(tmp_path):
    src = tmp_path / "video.ts"
    outjpg = tmp_path / "snap.jpg"
    src.write_text("dummy")
    outjpg.write_text("img")
    with mock.patch("subprocess.run") as mrun:
        mrun.return_value = types.SimpleNamespace(returncode=0)
        with mock.patch(
            "pathlib.Path.exists",
            side_effect=lambda s=None: (
                True if s is None else Path(s).name == "snap.jpg"
            ),
        ):
            assert ffmpeg.takeSnapshot(str(src), str(outjpg)) == str(outjpg)


def test_takeSnapshot_fail(tmp_path):
    src = tmp_path / "video.ts"
    outjpg = tmp_path / "snap.jpg"
    src.write_text("dummy")
    with mock.patch("subprocess.run") as mrun:
        mrun.return_value = types.SimpleNamespace(returncode=1)
        assert ffmpeg.takeSnapshot(str(src), str(outjpg)) is None


def test_takeSnapshot_no_file(tmp_path):
    src = tmp_path / "nofile.ts"
    outjpg = tmp_path / "snap.jpg"
    assert ffmpeg.takeSnapshot(str(src), str(outjpg)) is None
