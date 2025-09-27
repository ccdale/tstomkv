"""tvh module for tstomkv"""

import json
import sys

import requests

from tstomkv import errorNotify
from tstomkv.config import readConfig


class TVHError(Exception):
    pass


def sendToTvh(route, data=None):
    """Send a request to tvheadend"""
    try:
        cfg = readConfig()
        auth = (cfg["DEFAULT"]["tvhuser"], cfg["DEFAULT"]["tvhpass"])
        url = f"http://{cfg['DEFAULT']['tvhipaddr']}/api/{route}"
        r = requests.get(url, params=data, auth=auth)
        if r.status_code != 200:
            raise TVHError(f"error communicating with tvh: {r}")
        return r.json()
    except Exception as e:
        try:
            print(f"Error decoding json from tvh, trying again\n{e}")
            txt = r.text.replace(chr(25), " ")
            return json.loads(txt)
        except Exception as e:
            errorNotify(sys.exc_info()[2], e)


def allRecordings():
    try:
        route = "dvr/entry/grid_finished"
        data = {"limit": 9999}
        jdat = sendToTvh(route, data=data)
        return jdat["entries"], jdat["total"]
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)


def deleteRecording(uuid):
    try:
        data = {"uuid": uuid}
        sendToTvh("dvr/entry/remove", data)
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)


def fileMoved(src, dst):
    try:
        data = {"src": src, "dst": dst}
        sendToTvh("dvr/entry/filemoved", data)
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)
