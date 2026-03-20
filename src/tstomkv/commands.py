"""Command entry points for file transfer and conversion workflows."""

import os
import sys
import time
from pathlib import Path
from threading import Thread

import tstomkv
from tstomkv import errorNotify, progressBar
from tstomkv.config import readConfig
from tstomkv.ffmpeg import checkPercentDuration, convert_ts_to_mkv, videoDuration
from tstomkv.files import (
    getFile,
    pathManipulation,
    remoteCommand,
    remoteFileList,
    remoteFinalFileName,
    sendFile,
    stopNow,
)
from tstomkv.recordings import filteredTitles
from tstomkv.tvh import fileMoved


class StopAll(Exception):
    pass


class CopyError(Exception):
    pass


def transcodeFile(src, dst, statsfile, overwrite=False):
    """Run ffmpeg conversion and ensure destination directory exists."""
    dirname = os.path.dirname(dst)
    Path(dirname).mkdir(mode=0o755, exist_ok=True, parents=True)
    return convert_ts_to_mkv(src, dst, statsfile, overwrite=overwrite)


def humanTime(seconds):
    """Convert seconds to a compact human-readable format."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{int(h)}h {int(m)}m {int(s)}s"
    if m > 0:
        return f"{int(m)}m {int(s)}s"
    return f"{int(s)}s"


def doStats(statsfile, duration):
    """Read ffmpeg progress stats and display a terminal progress bar."""
    cn = 0
    holdoff = 5
    while not Path(statsfile).exists():
        time.sleep(holdoff)
        cn += 1
        if cn > 12:
            print("No stats file after 1 minute, giving up")
            return
    if duration > 0:
        inprogress = True
        lastelapsed = 0
        while inprogress:
            time.sleep(holdoff)
            with open(statsfile, "r") as sf:
                stats = {}
                lines = sf.readlines()
                for line in lines:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        stats[k] = v
                if "out_time_ms" in stats:
                    try:
                        elapsed = int(stats["out_time_ms"]) / 1_000_000
                    except ValueError:
                        elapsed = lastelapsed
                    lastelapsed = elapsed
                    progressBar(elapsed, duration)
                if "progress" in stats and stats["progress"] == "end":
                    inprogress = False
        print()
        print("Transcoding complete")
    else:
        print("No duration info, cannot show progress")


def kodimkv():
    print(f"{tstomkv.__appname__} version: {tstomkv.getVersion()}")
    cfg = readConfig()
    files = remoteFileList()
    print(f"{len(files)} Remote files")
    for fn in files:
        print(f"Remote file: {fn}")
    if len(sys.argv) > 1:
        skip = int(sys.argv[1])
    for src in files:
        if len(sys.argv) > 1 and skip > 0:
            print(f"Skipping {src}")
            skip -= 1
            continue
        if stopNow():
            raise StopAll("STOP file found, exiting")
        if cfg["mediaserver"].get("koditvdir") in src:
            replace = cfg["mediaserver"]["koditvdir"]
        elif cfg["mediaserver"].get("kodifilmdir") in src:
            replace = cfg["mediaserver"]["kodifilmdir"]
        else:
            print(f"Skipping {src} as not in tvdir or filmdir")
            continue
        fps = pathManipulation(src, replace=replace, mkdestdir=True)
        starttime = time.time()
        if not getFile(str(fps["src"]), str(fps["dest"]), banner=True):
            raise Exception(f"Failed to copy {fps['src']} to {fps['dest']}")
        endtime = time.time()
        print(
            f"Time taken to copy {fps['src']} to {fps['dest']}: {humanTime(endtime - starttime)}"
        )
        statsfile = str(fps["dest"]) + "-transcode.stats"
        fthread = Thread(
            target=transcodeFile,
            args=(str(fps["dest"]), str(fps["destmkv"]), statsfile),
            kwargs={"overwrite": True},
        )
        sthread = Thread(target=doStats, args=(statsfile, videoDuration(fps["dest"])))
        fthread.start()
        sthread.start()
        fthread.join()
        sthread.join()
        print(
            f"Transcoding and stats monitoring complete for {Path(fps['destmkv']).name}"
        )
        if checkPercentDuration(fps["dest"], fps["destmkv"]):
            print("Duration check OK")
            finalfn = remoteFinalFileName(fps["destmkv"])
            sendFile(str(fps["destmkv"]), finalfn, banner=True)
            remoteCommand(f'rm "{str(fps["src"])}"', banner=True)
        else:
            print("Duration check FAILED, not moving file or deleting source")
            raise CopyError("Duration check failed")
        nexttime = time.time()
        print(f"time taken: {humanTime(nexttime - endtime)}")


def tvhmkv():
    """Entry point for tvhmkv script."""
    try:
        print(f"Starting tvhmkv {tstomkv.getVersion()}")
        recs, titles = filteredTitles()
        print(f"{len(recs)} Transport Stream recordings found")
        for title in titles:
            for rec in titles[title]:
                if stopNow():
                    raise StopAll("STOP file found, exiting")
                if not rec["filename"].lower().endswith(".ts"):
                    print(f"Skipping {rec['filename']}")
                    continue
                fps = pathManipulation(
                    rec["filename"], replace="/var/lib/tvheadend", mkdestdir=True
                )
                starttime = time.time()
                if not getFile(str(fps["src"]), str(fps["dest"]), banner=True):
                    raise CopyError(f"Failed to copy {fps['src']} to {fps['dest']}")
                endtime = time.time()
                print(
                    f"Time taken to copy {fps['src']} to {fps['dest']}: {humanTime(endtime - starttime)}"
                )
                statsfile = str(fps["dest"]) + "-transcode.stats"
                fthread = Thread(
                    target=transcodeFile,
                    args=(str(fps["dest"]), str(fps["destmkv"]), statsfile),
                    kwargs={"overwrite": True},
                )
                sthread = Thread(
                    target=doStats, args=(statsfile, videoDuration(fps["dest"]))
                )
                fthread.start()
                sthread.start()
                fthread.join()
                sthread.join()
                print(
                    f"Transcoding and stats monitoring complete for {Path(fps['dest']).name}"
                )
                if checkPercentDuration(fps["dest"], fps["destmkv"]):
                    print("Duration check OK")
                    sendFile(str(fps["destmkv"]), str(fps["srcmkv"]), banner=True)
                    fileMoved(str(fps["src"]), str(fps["srcmkv"]))
                    remoteCommand(f'rm "{str(fps["src"])}"', banner=True)
                else:
                    print("Duration check FAILED, not moving file or deleting source")
                    raise CopyError("Duration check failed")
                nexttime = time.time()
                print(f"time taken: {humanTime(nexttime - endtime)}")
    except StopAll as e:
        errorNotify(sys.exc_info()[2], e)
        sys.exit(0)
    except CopyError as e:
        errorNotify(sys.exc_info()[2], e)
        sys.exit(1)
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)
        sys.exit(1)
