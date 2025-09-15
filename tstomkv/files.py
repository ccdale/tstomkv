#
# Copyright (c) 2023-2024, Chris Allison
#
#     This file is part of cliptube.
#
#     cliptube is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     cliptube is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with cliptube.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import sys

from fabric import Connection

from tstomkv import errorNotify
from tstomkv.config import expandPath, readConfig, writeConfig


def getOutputFileName(cfg, vtype="v"):
    try:
        # cfg = readConfig()
        fnum = int(cfg["youtube"]["filenumber"])
        nextn = fnum + 1
        if nextn > 99:
            nextn = 0
        cfg["youtube"]["filenumber"] = str(nextn)
        writeConfig(cfg)
        match vtype:
            case "v":
                idir = expandPath(f'~/{cfg["youtube"]["videodir"]}')
            case "p":
                idir = expandPath(f'~/{cfg["youtube"]["playlistdir"]}')
            case "i":
                idir = expandPath(f'~/{cfg["youtube"]["iplayerdir"]}')
        return f"{idir}/{fnum:0>2}"
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)


def sendFileTo(fn, vtype="v"):
    try:
        cfg = readConfig()
        mhost = cfg["mediaserver"]["host"]
        muser = cfg["mediaserver"]["user"]
        mkeyfn = expandPath(f'~/.ssh/{cfg["mediaserver"]["keyfn"]}')
        ckwargs = {"key_filename": mkeyfn}
        ofn = getOutputFileName(cfg, vtype=vtype)
        with Connection(host=mhost, user=muser, connect_kwargs=ckwargs) as c:
            c.put(fn, ofn)
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)


def sendFile(src, dst, banner=False):
    """send a file to the media server"""
    try:
        cfg = readConfig()
        mhost = cfg["mediaserver"]["host"]
        muser = cfg["mediaserver"]["user"]
        mkeyfn = expandPath(f'~/.ssh/{cfg["mediaserver"]["keyfn"]}')
        ckwargs = {"key_filename": mkeyfn}
        if banner:
            print(f"sending {src} to {mhost}:{dst}")
        with Connection(host=mhost, user=muser, connect_kwargs=ckwargs) as c:
            c.put(src, dst)
        return True
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)
        return False


def getFile(src, dst, banner=False):
    """get a file from the media server"""
    try:
        cfg = readConfig()
        mhost = cfg["mediaserver"]["host"]
        muser = cfg["mediaserver"]["user"]
        mkeyfn = expandPath(f'~/.ssh/{cfg["mediaserver"]["keyfn"]}')
        ckwargs = {"key_filename": mkeyfn}
        if banner:
            print(f"Retrieving {dst} from {mhost}:{src}")
        with Connection(host=mhost, user=muser, connect_kwargs=ckwargs) as c:
            c.get(src, dst)
        return True
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)
        return False


def fileSize(fn):
    try:
        return os.path.getsize(fn)
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)
        return -1


def homeDir():
    try:
        return os.path.expandvars("$HOME")
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)


def dirFileList(path, filterext=None):
    try:
        if os.path.isdir(path):
            tfn = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            fns = (
                [f for f in tfn if not f.endswith(filterext)]
                if filterext is not None
                else tfn
            )
            return fns
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)


def remoteFileList():
    """list files on the media server"""
    try:
        cfg = readConfig()
        mhost = cfg["mediaserver"]["host"]
        muser = cfg["mediaserver"]["user"]
        mkeyfn = expandPath(f'~/.ssh/{cfg["mediaserver"]["keyfn"]}')
        ckwargs = {"key_filename": mkeyfn}
        findcmd = f"find {cfg['mediaserver']['koditvdir']} {cfg['mediaserver']['kodifilmdir']} -name \\*ts"
        with Connection(host=mhost, user=muser, connect_kwargs=ckwargs) as c:
            result = c.run(findcmd, hide=True)
            files = result.stdout.strip().split("\n")
            return files
    except Exception as e:
        errorNotify(sys.exc_info()[1], e)
        return []


def remoteCommand(cmd):
    """run a command on the media server"""
    try:
        cfg = readConfig()
        mhost = cfg["mediaserver"]["host"]
        muser = cfg["mediaserver"]["user"]
        mkeyfn = expandPath(f'~/.ssh/{cfg["mediaserver"]["keyfn"]}')
        ckwargs = {"key_filename": mkeyfn}
        with Connection(host=mhost, user=muser, connect_kwargs=ckwargs) as c:
            result = c.run(cmd, hide=True)
            return result.stdout.strip()
    except Exception as e:
        errorNotify(sys.exc_info()[1], e)
        return ""
