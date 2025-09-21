import os
from unittest import mock

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tstomkv import config  # noqa: E402


def test_expandPath_expands_user(monkeypatch):
    p = "~/mydir/file.txt"
    expanded = config.expandPath(p)
    assert os.path.isabs(expanded)
    assert expanded.endswith("mydir/file.txt")


def test_readConfig_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tstomkv.config.expandPath", lambda p: str(tmp_path / "nope.cfg")
    )
    with mock.patch("tstomkv.config.__appname__", "testapp"):
        with mock.patch("pathlib.Path.exists", return_value=False):
            try:
                config.readConfig()
            except Exception as e:
                assert "cannot find config file" in str(e)


def test_readConfig_reads_file(tmp_path, monkeypatch):
    cfgfile = tmp_path / "test.cfg"
    cfgfile.write_text("[section]\nkey=val\n")
    monkeypatch.setattr("tstomkv.config.expandPath", lambda p: str(cfgfile))
    with mock.patch("tstomkv.config.__appname__", "testapp"):
        with mock.patch("pathlib.Path.exists", return_value=True):
            conf = config.readConfig()
            assert conf.has_section("section")
            assert conf.get("section", "key") == "val"


def test_writeConfig_writes_file(tmp_path, monkeypatch):
    cfgfile = tmp_path / "test.cfg"

    class DummyCfg:
        def write(self, f):
            f.write("written!")

    monkeypatch.setattr("tstomkv.config.expandPath", lambda p: str(cfgfile))
    with mock.patch("tstomkv.config.__appname__", "testapp"):
        config.writeConfig(DummyCfg())
        assert cfgfile.read_text() == "written!"
