from unittest import mock

import pytest

from tstomkv import shell


def test_listCmd_with_list():
    assert shell.listCmd(["ls", "-l"]) == ["ls", "-l"]


def test_listCmd_with_string():
    assert shell.listCmd("ls -l") == ["ls", "-l"]


def test_listCmd_with_invalid_type():
    with pytest.raises(Exception):
        shell.listCmd(123)


def test_shellCommand_success():
    with mock.patch("subprocess.run") as mrun:
        mrun.return_value = mock.Mock(
            stdout="ok", stderr="", returncode=0, check_returncode=lambda: None
        )
        out, err = shell.shellCommand(["echo", "hi"])
        assert out == "ok"
        assert err == ""


def test_shellCommand_fail_raises():
    with (
        mock.patch("subprocess.run") as mrun,
        mock.patch("tstomkv.errorRaise", side_effect=Exception("fail")),
    ):
        mrun.return_value = mock.Mock(
            stdout="out",
            stderr="err",
            returncode=1,
            check_returncode=mock.Mock(
                side_effect=shell.CalledProcessError(1, ["fail"])
            ),
        )
        with pytest.raises(Exception):
            shell.shellCommand(["fail"])


def test_shellCommand_canfail():
    with mock.patch("subprocess.run") as mrun:
        mrun.return_value = mock.Mock(
            stdout="out",
            stderr="err",
            returncode=1,
            check_returncode=lambda: (_ for _ in ()).throw(
                shell.CalledProcessError(1, ["fail"])
            ),
        )
        out, err = shell.shellCommand(["fail"], canfail=True)
        assert out == "out"
        assert err == "err"
