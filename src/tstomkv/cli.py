import os
import sys
import time
from pathlib import Path
from threading import Thread

import tstomkv
from tstomkv import progressBar
from tstomkv.config import readConfig
from tstomkv.ffmpeg import checkPercentDuration, convert_ts_to_mkv, videoDuration
from tstomkv.files import getFile, remoteCommand, remoteFileList, sendFile
from tstomkv.paths import pathManipulation, stopNow
from tstomkv.recordings import recordedTitles
from tstomkv.tvh import fileMoved


def transcodeFile(src, dst, statsfile, overwrite=False):
    """Initiate the transcoder for a given source file to a destination file"""
    dirname = os.path.dirname(dst)
    Path(dirname).mkdir(mode=0o755, exist_ok=True, parents=True)
    return convert_ts_to_mkv(src, dst, statsfile, overwrite=overwrite)


def doStats(statsfile, duration):
    """Read the stats file and show a progress bar"""
    cn = 0
    holdoff = 5
    while Path(statsfile).exists() is False:
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
                if "progress" in stats:
                    if stats["progress"] == "end":
                        inprogress = False
        print()  # newline after progress bar
        print("Transcoding complete")
    else:
        print("No duration info, cannot show progress")


def kodimkv():
    print(f"{tstomkv.__appname__} version: {tstomkv.getVersion()}")
    cfg = readConfig()
    files = remoteFileList()
    print(f"{len(files)} Remote files")
    if len(sys.argv) > 1:
        skip = int(sys.argv[1])
    for src in files:
        isfilm = False
        if len(sys.argv) > 1:
            if skip > 0:
                print(f"Skipping {src}")
                skip -= 1
                continue
        stopfn = "/".join([cfg["DEFAULT"]["transcodedir"], "STOP"])
        if Path(stopfn).exists() is True:
            raise Exception("STOP file found, exiting")
        if cfg["mediaserver"].get("koditvdir") in src:
            dest = src.replace(
                cfg["mediaserver"]["koditvdir"], cfg["DEFAULT"]["transcodedir"]
            )
            destdir = Path(dest).parent
        elif cfg["mediaserver"].get("kodifilmdir") in src:
            isfilm = True
            dest = src.replace(
                cfg["mediaserver"]["kodifilmdir"], cfg["DEFAULT"]["transcodedir"]
            )
            destdir = Path(dest).parent
        else:
            print(f"Skipping {src} as not in tvdir or filmdir")
            continue
        starttime = time.time()
        destdir.mkdir(mode=0o755, exist_ok=True, parents=True)
        if not getFile(src, dest, banner=True):
            raise Exception(f"Failed to copy {src} to {dest}")
        endtime = time.time()
        print(f"Time taken to copy {src} to {dest}: {humanTime(endtime - starttime)}")
        tsrc = dest
        tdest = dest.replace(".ts", ".mkv")
        vduration = videoDuration(tsrc)
        statsfile = str(tsrc) + "-transcode.stats"
        fthread = Thread(
            target=transcodeFile,
            args=(tsrc, tdest, statsfile),
            kwargs={"overwrite": True},
        )
        sthread = Thread(target=doStats, args=(statsfile, vduration))
        fthread.start()
        sthread.start()
        fthread.join()
        sthread.join()
        print(f"Transcoding and stats monitoring complete for {Path(tdest).name}")
        nexttime = time.time()
        print(f"time taken: {humanTime(nexttime - endtime)}")
        if isfilm:
            # move the file to the film directory
            dest = tdest.replace(
                cfg["DEFAULT"]["transcodedir"], cfg["mediaserver"]["kodifilmdir"]
            )
        else:
            dest = tdest.replace(
                cfg["DEFAULT"]["transcodedir"], cfg["mediaserver"]["koditvdir"]
            )
        if not sendFile(tdest, dest, banner=True):
            raise Exception(f"Failed to send {tdest} to {dest}")
        print(f"time taken to send file: {humanTime(time.time() - nexttime)}")
        res = remoteCommand(f"rm '{src}'", banner=True)
        if res != "":
            raise Exception(f"Failed to remove remote file {src}")
        print(f"process time for {src}: {humanTime(time.time() - starttime)}")


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


def tvhmkv():
    """Entry point for tvhmkv script"""
    try:
        print(f"Starting tvhmkv {tstomkv.getVersion()}")
        recs, titles = recordedTitles()
        print(f"{len(recs)} recordings found")
        for title in titles:
            for rec in titles[title]:
                if not rec["filename"].lower().endswith(".ts"):
                    print(f"Skipping {rec['filename']} as not a .ts file")
                    continue
                fps = pathManipulation(
                    rec["filename"], replace="/var/lib/tvheadend", mkdestdir=True
                )
                if stopNow():
                    raise Exception("STOP file found, exiting")
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
                sthread = Thread(
                    target=doStats, args=(statsfile, videoDuration(fps["dest"]))
                )
                fthread.start()
                sthread.start()
                fthread.join()
                sthread.join()
                print(
                    f"Transcoding and stats monitoring complete for {Path(fps["dest"]).name}"
                )
                if checkPercentDuration(fps["dest"], fps["destmkv"]):
                    print("Duration check OK")
                    sendFile(str(fps["destmkv"]), str(fps["srcmkv"]), banner=True)
                    fileMoved(str(fps["src"]), str(fps["srcmkv"]))
                    remoteCommand(f"rm '{str(fps['src'])}'", banner=True)
                nexttime = time.time()
                print(f"time taken: {humanTime(nexttime - endtime)}")
    except Exception as e:
        tstomkv.errorRaise(f"tvhmkv failed: {e}")
