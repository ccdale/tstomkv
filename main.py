import os
import time
from pathlib import Path
from threading import Thread

import tstomkv
from tstomkv import progressBar
from tstomkv.config import readConfig
from tstomkv.ffmpeg import convert_ts_to_mkv, videoDuration
from tstomkv.files import getFile, remoteCommand, remoteFileList, sendFile


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


def main():
    print(f"{tstomkv.__appname__} version: {tstomkv.getVersion()}")
    cfg = readConfig()
    files = remoteFileList()
    print(f"{len(files)} Remote files")
    for src in files:
        stopfn = "/".join([cfg["DEFAULT"]["transcodedir"], "STOP"])
        if Path.exists(stopfn) is True:
            raise Exception("STOP file found, exiting")
        if cfg["mediaserver"].get("koditvdir") in src:
            dest = src.replace(
                cfg["mediaserver"]["koditvdir"], cfg["DEFAULT"]["transcodedir"]
            )
            destdir = Path(dest).parent
        elif cfg["mediaserver"].get("kodifilmdir") in src:
            dest = src.replace(
                cfg["mediaserver"]["kodifilmdir"], cfg["DEFAULT"]["transcodedir"]
            )
            destdir = Path(dest).parent
        else:
            print(f"Skipping {src} as not in tvdir or filmdir")
            continue

        destdir.mkdir(mode=0o755, exist_ok=True, parents=True)
        if not getFile(src, dest):
            raise Exception(f"Failed to copy {src} to {dest}")
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
        dest = tdest.replace(
            cfg["DEFAULT"]["transcodedir"], cfg["mediaserver"]["koditvdir"]
        )
        if not sendFile(tdest, dest, banner=True):
            raise Exception(f"Failed to send {tdest} to {dest}")
        res = remoteCommand(f"rm '{src}'")
        if res != "":
            raise Exception(f"Failed to remove remote file {src}")


if __name__ == "__main__":
    main()
