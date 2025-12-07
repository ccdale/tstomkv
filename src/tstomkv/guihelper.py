import sys

from tstomkv import errorExit, errorNotify, errorRaise


def transcodeFile(src, dst, statsfile, overwrite=False):
    """Initiate the transcoder for a given source file to a destination file"""
    dirname = os.path.dirname(dst)
    Path(dirname).mkdir(mode=0o755, exist_ok=True, parents=True)
    return convert_ts_to_mkv(src, dst, statsfile, overwrite=overwrite)


def humanTime(seconds):
    """convert seconds to human readable time"""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{int(h)}h {int(m)}m {int(s)}s"
    elif m > 0:
        return f"{int(m)}m {int(s)}s"
    else:
        return f"{int(s)}s"
