"""ffmpeg module for transport stream to mkv application."""

import json
import os
import subprocess
import sys
from pathlib import Path

from tstomkv import errorRaise
from tstomkv.shell import shellCommand


def convert_ts_to_mkv(
    input_file: str, output_file: str, statsfile: str, overwrite=False
):
    """transcode a transport stream file to mkv x265/aac"""
    try:
        if not input_file.lower().endswith(".ts"):
            raise ValueError("Input file must be a .ts file")
        if not output_file.endswith(".mkv"):
            raise ValueError("Output file must be a .mkv file")
        if not overwrite and removeFileIfExists(output_file, reportOnly=True):
            raise FileExistsError(
                f"Output file {output_file} exists and overwrite is False"
            )
        else:
            removeFileIfExists(output_file)
        print(f"Transcoding {input_file} to {output_file}...")
        # options:
        # -stats_period 5 - write stats every 5 seconds to statsfile
        # -progress statsfile - changes the output of ffmpeg to
        #     issuing progress tables every stats_period
        # -c:v libx265 - use h265 encoding
        # -preset medium - use preset medium (default, but hey-ho)
        # -c:a aac -b:a 128k - use aac encoding for audio at a bitrate of 128k
        # -c:s copy -map 0 - copy the dvb subtitles as is
        #     (which is why we have to use a matroska container)

        cmd = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-hide_banner",
            "-progress",
            statsfile,
            "-stats_period",
            "5",
            "-i",
            input_file,
            "-c:v",
            "libx265",
            "-preset",
            "medium",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-c:s",
            "copy",
            output_file,
        ]
        _, _ = shellCommand(cmd, canfail=True)
        print(f"Conversion complete: {output_file}")
    except Exception as e:
        errorRaise(sys.exc_info()[2], e)


def removeFileIfExists(infile, reportOnly=False):
    """delete the file if it exists, unless reportOnly is True"""
    try:
        fn = Path(infile)
        if fn.exists():
            if reportOnly:
                return True
            else:
                os.remove(fn)
                return True
        return False
    except Exception as e:
        errorRaise(sys.exc_info()[2], e)


def fileInfo(fqfn):
    """use ffprobe. returns dict of fileinfo or None."""
    try:
        fn = Path(fqfn)
        if fn.exists():
            cmd = [
                "ffprobe",
                "-loglevel",
                "quiet",
                "-of",
                "json",
                "-show_streams",
                fqfn,
            ]
            proc = subprocess.run(cmd, capture_output=True)
            if proc.returncode == 0:
                xstr = proc.stdout.decode("utf-8")
                # print(xstr)
                return json.loads(xstr)
    except Exception as e:
        errorRaise(sys.exc_info()[2], e)


def takeSnapshot(src, outjpg, location="40"):
    """Takes a jpeg snapshot from src video file at location seconds into outjpg"""  # noqa: E501
    try:
        fn = Path(src)
        if fn.exists():
            cmd = [
                "ffmpeg",
                "-ss",
                location,
                "-i",
                src,
                "-frames:v",
                "1",
                outjpg,
            ]  # noqa: E501
            proc = subprocess.run(cmd)
            if proc.returncode == 0:
                ofn = Path(outjpg)
                if ofn.exists():
                    return outjpg
    except Exception as e:
        errorRaise(sys.exc_info()[2], e)


def videoDuration(fqfn):
    """use ffprobe. returns duration in seconds or None."""
    try:
        finfo = fileInfo(fqfn)
        if finfo and "streams" in finfo:
            for stream in finfo["streams"]:
                if "codec_type" in stream and stream["codec_type"] == "video":
                    if "duration" in stream:
                        # no need to be exact, just return int seconds
                        return int(float(stream["duration"]))
        return None
    except Exception as e:
        errorRaise(sys.exc_info()[2], e)
        return None


def checkPercentDuration(fn1, fn2, threshold=0.9):
    """Check that the duration of fn2 is at least threshold percent of fn1"""
    try:
        dur1 = videoDuration(fn1)
        dur2 = videoDuration(fn2)
        if dur1 and dur2:
            if dur2 >= (dur1 * threshold):
                return True
        return False
    except Exception as e:
        errorRaise(sys.exc_info()[2], e)
        return False
