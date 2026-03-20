# tstomkv

tstomkv converts TV recordings from Transport Stream files (.ts) into Matroska files (.mkv).

It is built for a TVHeadend-based workflow and supports both:

- a GTK4 desktop app for browsing and converting selected recordings
- a CLI workflow for batch processing

## Why It Exists

tstomkv helps automate a repetitive media workflow:

1. Find .ts recordings from TVHeadend.
2. Copy them locally for conversion.
3. Convert with ffmpeg.
4. Push converted .mkv files back to the media server.
5. Notify TVHeadend and clean up source files.

Matroska is used because it handles subtitle/container combinations needed by this workflow.

## Quick Start

```bash
uv sync
uv run gtk4titles
```

Useful CLI entry points:

- uv run tvhmkv
- uv run kodimkv

## Requirements

- Linux
- Python 3.13+
- ffmpeg and ffprobe on PATH
- TVHeadend API access
- SSH access to media server
- GTK4 and PyGObject for GUI mode

## Configuration

tstomkv reads config from:

```text
~/.config/tstomkv.cfg
```

See the maintainer guide for a complete config example and deeper technical details:

- [MAINTAINER.md](MAINTAINER.md)

## Acknowledgement

This GTK4 application was built with enormous help from GitHub Copilot.

At the start of this migration, I knew essentially nothing about GTK4. Copilot helped me design, iterate, debug, and test the application as I learned.

## For Maintainers

Technical architecture, workflow internals, release notes, and operational caveats are documented in:

- [MAINTAINER.md](MAINTAINER.md)