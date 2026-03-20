"""Compatibility facade for GTK4 filtered titles app modules."""

import sys

from tstomkv import errorNotify

from .gtk4_app import FilteredTitlesApp, FilteredTitlesWindow
from .gtk4_formatting import (
    _build_title_rows,
    _display_title,
    _format_conversion_list,
    _format_filtered_titles,
    _format_title_details,
    _sort_key,
    _sorted_recordings_for_title,
)
from .gtk4_runtime import Gtk
from .gtk4_transfer import (
    FileCopyProgressDialog,
    _calculate_progress,
    _format_elapsed_mmss,
    _format_transfer_status,
    copy_file_with_progress,
)

__all__ = [
    "Gtk",
    "FilteredTitlesApp",
    "FilteredTitlesWindow",
    "FileCopyProgressDialog",
    "copy_file_with_progress",
    "_build_title_rows",
    "_calculate_progress",
    "_display_title",
    "_format_elapsed_mmss",
    "_format_conversion_list",
    "_format_filtered_titles",
    "_format_title_details",
    "_format_transfer_status",
    "_sort_key",
    "_sorted_recordings_for_title",
    "main",
]


def main():
    """Entry point for the GTK4 filteredTitles viewer."""
    if Gtk is None:
        print("GTK4 unavailable: install PyGObject with `uv sync`.")
        return 1

    try:
        app = FilteredTitlesApp()
        return app.run(sys.argv)
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
