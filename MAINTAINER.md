# tstomkv Maintainer Guide

This document is the technical companion to [README.md](README.md).

## Scope

tstomkv is a TVHeadend-oriented media conversion workflow that:

1. Retrieves recording metadata from TVHeadend.
2. Copies source .ts files over SSH.
3. Converts to .mkv with ffmpeg.
4. Publishes outputs back to remote storage.
5. Notifies TVHeadend and removes source files.

Primary interfaces:

- GTK4 app entry point: uv run gtk4titles
- CLI entry points: uv run tvhmkv and uv run kodimkv

## Code Layout

- [src/tstomkv/gtk4.py](src/tstomkv/gtk4.py): GTK4 compatibility facade and app entry point
- [src/tstomkv/gtk4_app.py](src/tstomkv/gtk4_app.py): main GTK4 window and app wrapper
- [src/tstomkv/gtk4_transfer.py](src/tstomkv/gtk4_transfer.py): transfer, conversion, publish workflow helpers and progress dialog
- [src/tstomkv/commands.py](src/tstomkv/commands.py): CLI command entry points
- [src/tstomkv/ffmpeg.py](src/tstomkv/ffmpeg.py): ffmpeg and ffprobe integration
- [src/tstomkv/files.py](src/tstomkv/files.py): SSH transfer and remote command utilities (Fabric)
- [src/tstomkv/recordings.py](src/tstomkv/recordings.py): TVHeadend recording normalization and filtering
- [src/tstomkv/tvh.py](src/tstomkv/tvh.py): TVHeadend API calls
- [src/tstomkv/config.py](src/tstomkv/config.py): config read and write helpers

## Runtime Dependencies

- Python 3.13+
- ffmpeg
- ffprobe
- TVHeadend API reachability
- SSH key-based access to media server
- GTK4 + PyGObject (GUI mode)

Python dependencies are in [pyproject.toml](pyproject.toml).

## Configuration

Config file path:

```text
~/.config/tstomkv.cfg
```

Example:

```ini
[DEFAULT]
tvhuser = your_tvh_user
tvhpass = your_tvh_password
tvhipaddr = 192.168.1.100:9981
transcodedir = /home/you/tmp/transcode

[mediaserver]
host = media-server.local
user = your_ssh_user
keyfn = id_ed25519
koditvdir = /srv/media/tv
kodifilmdir = /srv/media/films
```

Operational notes:

- keyfn is resolved from ~/.ssh/
- transcodedir is a local working directory
- STOP file support exists via files.stopNow and uses transcodedir/STOP

## Workflow Notes

### GTK4 flow

1. Load filtered titles from TVHeadend.
2. User selects title rows.
3. For each source file, copy source from remote to local.
4. Convert to mkv and publish verified output.
5. Send completion notification when possible.

The transfer/publish workflow in [src/tstomkv/gtk4_transfer.py](src/tstomkv/gtk4_transfer.py) includes checksum checks for safer publish behavior.

### CLI flow

The CLI commands in [src/tstomkv/commands.py](src/tstomkv/commands.py) run a similar copy/convert/publish pipeline from script entry points.

## Desktop Integration

Project icon assets:

- [assets/tstomkv-icon.svg](assets/tstomkv-icon.svg)
- [assets/png/tstomkv-icon-256.png](assets/png/tstomkv-icon-256.png)
- [assets/png/tstomkv-icon-512.png](assets/png/tstomkv-icon-512.png)

Local desktop file (user install):

- ~/.local/share/applications/tstomkv.desktop

If launcher metadata changes, validate with:

```bash
desktop-file-validate ~/.local/share/applications/tstomkv.desktop
```

## Development

Install dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run pytest -q
```

## Known Caveats

- Remote command and transfer errors are environment-specific and can fail silently if credentials or host paths drift.
- Desktop shell icon behavior may vary by compositor/session even when GTK icon hooks are set.
- Some legacy comments and naming in source modules predate current repository naming.

## Acknowledgement

This GTK4 migration was built with major assistance from GitHub Copilot.

Project context from the author:

- Starting point: no practical GTK4 knowledge
- Outcome: working GTK4 application with tested transfer and conversion workflow
