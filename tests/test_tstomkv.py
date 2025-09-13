from unittest import mock
from unittest.mock import patch

import pytest

import tstomkv


def test_errorNotify_prints_message(capfd):
    class DummyExci:
        tb_lineno = 42
        tb_frame = type(
            "Frame",
            (),
            {"f_code": type("Code", (), {"co_name": "dummy_func"})},  # noqa: E501
        )()

    e = ValueError("test error")
    tstomkv.errorNotify(DummyExci, e)
    out, _ = capfd.readouterr()
    estr = "ValueError Exception at line 42 in function dummy_func: test error"
    assert estr in out


def test_errorRaise_raises_exception():
    class DummyExci:
        tb_lineno = 1
        tb_frame = type(
            "Frame", (), {"f_code": type("Code", (), {"co_name": "func"})}
        )()

    e = RuntimeError("fail")
    with pytest.raises(RuntimeError):
        tstomkv.errorRaise(DummyExci, e)


def test_errorExit_exits(monkeypatch):
    class DummyExci:
        tb_lineno = 1
        tb_frame = type(
            "Frame", (), {"f_code": type("Code", (), {"co_name": "func"})}
        )()

    e = RuntimeError("fail")
    with pytest.raises(SystemExit):
        tstomkv.errorExit(DummyExci, e)


def test_gitroot_success(monkeypatch):
    with mock.patch("subprocess.check_output", return_value="/tmp\n"):
        assert tstomkv.gitroot() == "/tmp"


def test_gitroot_failure(monkeypatch):
    with mock.patch("subprocess.check_output", side_effect=Exception("fail")):
        with pytest.raises(SystemExit):
            tstomkv.gitroot()


def test_getVersion_success(monkeypatch, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "1.2.3"\n')
    with mock.patch("tstomkv.gitroot", return_value=str(tmp_path)):
        assert tstomkv.getVersion() == "1.2.3"


def test_getVersion_no_gitroot(monkeypatch):
    with mock.patch("tstomkv.gitroot", return_value=""):
        assert tstomkv.getVersion() == "0.0.0"


def test_getVersion_no_pyproject(monkeypatch, tmp_path):
    with mock.patch("tstomkv.gitroot", return_value=str(tmp_path)):
        assert tstomkv.getVersion() == "0.0.0"


def test_getVersion_toml_error(monkeypatch):
    with (
        mock.patch("tstomkv.gitroot", return_value="/tmp"),
        mock.patch("builtins.open", side_effect=Exception("fail")),
    ):
        assert tstomkv.getVersion() == "0.0.0"


class TestProgressBar:
    """Test the progressBar function."""

    @patch("builtins.print")
    def test_progressBar_basic(self, mock_print):
        """Test basic progress bar functionality."""
        tstomkv.progressBar(25, 100)

        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        assert "|" in call_args
        assert "25.00" in call_args

    @patch("builtins.print")
    def test_progressBar_with_values(self, mock_print):
        """Test progress bar with showValues=True."""
        tstomkv.progressBar(5, 20, showValues=True)

        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        assert "5 / 20" in call_args

    @patch("builtins.print")
    def test_progressBar_remove_with_newline(self, mock_print):
        """Test progress bar removal with newline."""
        tstomkv.progressBar(10, 10, remove=True, newline=True)

        # Should print twice - once for progress, once for removal
        assert mock_print.call_count == 2

    @patch("builtins.print")
    @patch("tstomkv.errorNotify")
    def test_progressBar_exception_handling(
        self, mock_error_notify, mock_print
    ):  # noqa: E501
        """Test progress bar exception handling."""
        # Cause a division by zero error
        tstomkv.progressBar(5, 0)

        mock_error_notify.assert_called_once()
