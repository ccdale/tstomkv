# tstomkv

A simple tool to convert TS files to MKV containered files, shrinking their size if possible.

Heavy lifting is performed by `ffmpeg` and the `H265` video codec. Audio streams are converted to `AAC` format and `DVB` subtitles are copied across (which is why the output is a Matroska container as that handles `dvb_subtitle` streams).