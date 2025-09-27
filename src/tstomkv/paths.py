import sys
from pathlib import Path

from tstomkv import errorNotify
from tstomkv.config import readConfig


def pathManipulation(src, replace="/var/lib/tvheadend", mkdestdir=True):
    try:
        op = {}
        cfg = readConfig()
        op["src"] = Path(src)
        op["srcmkv"] = op["src"].with_suffix(".mkv")
        op["srcdir"] = op["src"].parent
        op["dest"] = Path(src.replace(replace, cfg["DEFAULT"]["transcodedir"]))
        op["destmkv"] = op["dest"].with_suffix(".mkv")
        op["destdir"] = op["dest"].parent
        if mkdestdir:
            op["destdir"].mkdir(mode=0o755, exist_ok=True, parents=True)
        return op
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)


def stopNow():
    """Stop the transcoding process"""
    cfg = readConfig()
    stopfn = "/".join([cfg["DEFAULT"]["transcodedir"], "STOP"])
    return Path(stopfn).exists()
