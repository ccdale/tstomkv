import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tstomkv import paths


def test_pathManipulation_basic(tmp_path):
    src = tmp_path / "video" / "foo.ts"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("dummy")
    cfg = {"DEFAULT": {"transcodedir": str(tmp_path / "transcoded")}}
    with mock.patch("tstomkv.paths.readConfig", return_value=cfg):
        result = paths.pathManipulation(str(src), replace=str(tmp_path))
        assert result["src"] == src
        assert result["srcmkv"] == src.with_suffix(".mkv")
        assert result["srcdir"] == src.parent
        assert str(result["dest"]).startswith(str(tmp_path / "transcoded"))
        assert result["destmkv"] == result["dest"].with_suffix(".mkv")
        assert result["destdir"] == result["dest"].parent
        assert result["destdir"].exists()


def test_pathManipulation_no_mkdestdir(tmp_path):
    src = tmp_path / "video" / "foo.ts"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("dummy")
    cfg = {"DEFAULT": {"transcodedir": str(tmp_path / "transcoded")}}
    with mock.patch("tstomkv.paths.readConfig", return_value=cfg):
        result = paths.pathManipulation(
            str(src), replace=str(tmp_path), mkdestdir=False
        )
        assert result["destdir"].exists() is False
