import sys
import time
from pathlib import Path
from threading import Thread

import tstomkv
from tstomkv import errorExit


def transcodeFile(src, dst, statsfile, overwrite=False):
    """Initiate the transcoder for a given source file to a destination file"""
    dirname = os.path.dirname(dst)
    Path(dirname).mkdir(mode=0o755, exist_ok=True, parents=True)
    return convert_ts_to_mkv(src, dst, statsfile, overwrite=overwrite)


def doTstomkv():
    """Process a transport stream with x265/aac encoding to mkv"""
    try:
        # Your transcoding logic here
        pass
    except Exception as e:
        errorExit(sys.exc_info()[2], e)
