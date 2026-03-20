"""GTK4 app that displays the output of recordings.filteredTitles()."""

import os
import sys
import threading
import time
from pathlib import Path

import tstomkv
from tstomkv import errorNotify
from tstomkv.files import getFile, remoteFileSize
from tstomkv.recordings import filteredTitles

try:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
except (ImportError, ValueError):
    Gtk = None


def _display_title(title):
    return str(title) if title else "<No title>"


def _sort_key(value):
    return _display_title(value).lower()


def _sorted_recordings_for_title(recordings):
    return sorted(recordings, key=lambda rec: rec.get("filename") or "")


def _build_title_rows(titles):
    """Build sorted rows for the title list UI and text rendering."""
    rows = []
    for title in sorted(titles.keys(), key=_sort_key):
        recordings = _sorted_recordings_for_title(titles[title])
        rows.append(
            {
                "title": title,
                "display": _display_title(title),
                "count": len(recordings),
                "recordings": recordings,
            }
        )
    return rows


def _format_title_details(title, recordings):
    """Return details text for one selected title."""
    heading = _display_title(title)
    lines = [f"{heading}", f"Recordings: {len(recordings)}", ""]

    for rec in recordings:
        filename = rec.get("filename") or "<unknown>"
        subtitle = rec.get("subtitle")
        channel = rec.get("channelname")
        episode = rec.get("episode")
        season = rec.get("season")

        if subtitle:
            lines.append(f"- {subtitle}")
        else:
            lines.append("- <No subtitle>")

        lines.append(f"  file: {filename}")
        if channel:
            lines.append(f"  channel: {channel}")
        if season or episode:
            lines.append(f"  episode: S{season or '?'} E{episode or '?'}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_filtered_titles(recs, titles):
    """Create readable text output from filteredTitles()."""
    rows = _build_title_rows(titles)
    lines = [
        f"Transport Stream recordings: {len(recs)}",
        f"Unique titles: {len(rows)}",
        "",
    ]

    if not rows:
        lines.append("No recordings returned by filteredTitles().")
        return "\n".join(lines) + "\n"

    for row in rows:
        lines.append(f"{row['display']} ({row['count']})")
        for rec in row["recordings"]:
            filename = rec.get("filename") or "<unknown>"
            subtitle = rec.get("subtitle")
            if subtitle:
                lines.append(f"  - {subtitle}: {filename}")
            else:
                lines.append(f"  - {filename}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_conversion_list(selected_titles_data):
    """Format selected titles into a conversion list."""
    if not selected_titles_data:
        return "No titles selected for conversion.\n"

    lines = ["Conversion List", "=" * 40, ""]
    for row_data in selected_titles_data:
        title = row_data["display"]
        count = row_data["count"]
        recordings = row_data["recordings"]

        lines.append(f"{title} ({count} recording{'' if count == 1 else 's'})")
        for rec in recordings:
            filename = rec.get("filename") or "<unknown>"
            lines.append(f"  {filename}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _calculate_progress(src_size, dst_path, elapsed_time):
    """Calculate transfer progress as a fraction (0.0-1.0).

    Args:
        src_size: Total file size in bytes from remote.
        dst_path: Local destination file path.
        elapsed_time: Seconds elapsed since transfer started.

    Returns:
        Tuple of (progress_fraction, bytes_transferred, transfer_rate_average).
    """
    if src_size <= 0:
        return 0.0, 0, 0.0

    try:
        if not Path(dst_path).exists():
            return 0.0, 0, 0.0

        dst_size = os.path.getsize(dst_path)
        fraction = min(1.0, dst_size / src_size)
        rate = dst_size / elapsed_time if elapsed_time > 0 else 0.0
        return fraction, dst_size, rate
    except Exception:
        return 0.0, 0, 0.0


def _format_transfer_status(filename, src_size, dst_size, elapsed, rate):
    """Format a human-readable transfer status message.

    Args:
        filename: Name of the file being transferred.
        src_size: Total bytes on remote.
        dst_size: Bytes received locally.
        elapsed: Seconds elapsed.
        rate: Average bytes per second.

    Returns:
        Formatted status string.
    """
    from tstomkv.files import humanSize

    src_human = humanSize(src_size)
    dst_human = humanSize(dst_size)
    rate_human = humanSize(rate) if rate > 0 else "0.00 B"
    percent = (dst_size / src_size * 100) if src_size > 0 else 0.0

    return f"{filename}: {dst_human}/{src_human} ({percent:.1f}%) at {rate_human}/s"


def copy_file_with_progress(src, dst, callback=None, error_callback=None):
    """Copy a file from remote media server with progress monitoring.

    Runs in a background thread, calling callback periodically with progress data.
    """

    def _do_copy():
        try:
            src_size = remoteFileSize(src)
            if src_size < 0:
                if error_callback:
                    error_callback(f"Could not determine remote file size for {src}")
                return

            start_time = time.time()
            success = getFile(src, dst, banner=False)
            if not success:
                if error_callback:
                    error_callback(f"Failed to copy {src} to {dst}")
                return

            elapsed = time.time() - start_time
            progress, bytes_tx, rate = _calculate_progress(src_size, dst, elapsed)
            if callback:
                callback(progress=1.0, status="Transfer complete", finished=True)
        except Exception as e:
            if error_callback:
                error_callback(str(e))

    thread = threading.Thread(target=_do_copy, daemon=False)
    thread.start()


if Gtk is not None:

    class FileCopyProgressDialog(Gtk.ApplicationWindow):
        """GTK4 progress dialog for copying files from media server."""

        def __init__(self, application, src, dst):
            super().__init__(application=application)
            self.set_title("Copying file from Media Server")
            self.set_default_size(500, 200)
            self.set_modal(True)
            self.src = src
            self.dst = dst
            self._cancelled = False
            self._finished = False

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.set_margin_top(20)
            box.set_margin_bottom(20)
            box.set_margin_start(20)
            box.set_margin_end(20)

            filename_label = Gtk.Label(label=f"Copying: {Path(src).name}")
            filename_label.set_xalign(0)
            box.append(filename_label)

            self.status_label = Gtk.Label(label="Starting transfer...")
            self.status_label.set_xalign(0)
            self.status_label.set_wrap(True)
            box.append(self.status_label)

            self.progress_bar = Gtk.ProgressBar()
            self.progress_bar.set_fraction(0.0)
            box.append(self.progress_bar)

            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            button_box.set_halign(Gtk.Align.END)

            self.cancel_btn = Gtk.Button(label="Cancel")
            self.cancel_btn.connect("clicked", self._on_cancel_clicked)
            button_box.append(self.cancel_btn)

            close_btn = Gtk.Button(label="Close")
            close_btn.connect("clicked", lambda _: self.close())
            close_btn.set_sensitive(False)
            self.close_btn = close_btn
            button_box.append(close_btn)

            box.append(button_box)
            self.set_child(box)

            self._start_copy()

        def _on_cancel_clicked(self, _button):
            self._cancelled = True
            self.cancel_btn.set_sensitive(False)
            self.status_label.set_text("Cancellation requested...")

        def _on_copy_progress(self, progress, status, finished=False):
            def _update_ui():
                self.progress_bar.set_fraction(progress)
                self.status_label.set_text(status)
                if finished:
                    self._finished = True
                    self.cancel_btn.set_sensitive(False)
                    self.close_btn.set_sensitive(True)

            if Gtk:
                from gi.repository import GLib

                GLib.idle_add(_update_ui)

        def _on_copy_error(self, error_msg):
            def _show_error():
                self.status_label.set_text(f"Error: {error_msg}")
                self._finished = True
                self.cancel_btn.set_sensitive(False)
                self.close_btn.set_sensitive(True)

            if Gtk:
                from gi.repository import GLib

                GLib.idle_add(_show_error)

        def _monitor_progress(self):
            """Monitor transfer progress in background thread."""
            try:
                src_size = remoteFileSize(self.src)
                if src_size < 0:
                    self._on_copy_error(f"Could not determine file size for {self.src}")
                    return

                start_time = time.time()
                while not self._finished and not self._cancelled:
                    elapsed = time.time() - start_time
                    fraction, bytes_tx, rate = _calculate_progress(
                        src_size, self.dst, elapsed
                    )
                    status = _format_transfer_status(
                        Path(self.src).name, src_size, bytes_tx, elapsed, rate
                    )
                    self._on_copy_progress(fraction, status, finished=False)
                    time.sleep(0.5)

            except Exception as e:
                self._on_copy_error(str(e))

        def _start_copy(self):
            """Start the file copy in background threads."""
            monitor_thread = threading.Thread(
                target=self._monitor_progress, daemon=True
            )
            monitor_thread.start()

            def _copy_file():
                try:
                    success = getFile(self.src, self.dst, banner=False)
                    if success:
                        self._on_copy_progress(1.0, "Transfer complete", finished=True)
                    else:
                        self._on_copy_error(f"Failed to copy {self.src}")
                except Exception as e:
                    self._on_copy_error(str(e))

            copy_thread = threading.Thread(target=_copy_file, daemon=True)
            copy_thread.start()

    class FilteredTitlesWindow(Gtk.ApplicationWindow):
        """Main GTK4 window for displaying filtered titles."""

        def __init__(self, application):
            super().__init__(application=application)
            self.set_title(f"tstomkv GTK4 - {tstomkv.getVersion()}")
            self.set_default_size(980, 700)
            self._rows = []
            self._title_checkboxes = {}

            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            outer.set_margin_top(10)
            outer.set_margin_bottom(10)
            outer.set_margin_start(10)
            outer.set_margin_end(10)

            controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            refresh_btn = Gtk.Button(label="Refresh")
            refresh_btn.connect("clicked", self._on_refresh_clicked)
            controls.append(refresh_btn)

            select_all_btn = Gtk.Button(label="Select All")
            select_all_btn.connect("clicked", self._on_select_all_clicked)
            controls.append(select_all_btn)

            deselect_all_btn = Gtk.Button(label="Deselect All")
            deselect_all_btn.connect("clicked", self._on_deselect_all_clicked)
            controls.append(deselect_all_btn)

            show_list_btn = Gtk.Button(label="Show Conversion List")
            show_list_btn.connect("clicked", self._on_show_conversion_list_clicked)
            controls.append(show_list_btn)

            copy_btn = Gtk.Button(label="Copy Files to Temp")
            copy_btn.connect("clicked", self._on_copy_files_clicked)
            controls.append(copy_btn)

            self.status_label = Gtk.Label(label="Ready")
            self.status_label.set_xalign(0)
            controls.append(self.status_label)
            outer.append(controls)

            split = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
            split.set_wide_handle(True)

            left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            left_label = Gtk.Label(label="Titles (check to select for conversion)")
            left_label.set_xalign(0)
            left_box.append(left_label)

            left_scroll = Gtk.ScrolledWindow()
            left_scroll.set_hexpand(True)
            left_scroll.set_vexpand(True)
            self.title_list = Gtk.ListBox()
            self.title_list.connect("row-selected", self._on_title_selected)
            left_scroll.set_child(self.title_list)
            left_box.append(left_scroll)

            right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            right_label = Gtk.Label(label="Recording Details")
            right_label.set_xalign(0)
            right_box.append(right_label)

            right_scroll = Gtk.ScrolledWindow()
            right_scroll.set_hexpand(True)
            right_scroll.set_vexpand(True)
            self.text_view = Gtk.TextView()
            self.text_view.set_editable(False)
            self.text_view.set_monospace(True)
            self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            right_scroll.set_child(self.text_view)
            right_box.append(right_scroll)

            split.set_start_child(left_box)
            split.set_end_child(right_box)
            split.set_position(320)
            outer.append(split)

            self.set_child(outer)
            self.refresh_data()

        def _on_refresh_clicked(self, _button):
            self.refresh_data()

        def _on_select_all_clicked(self, _button):
            for checkbox in self._title_checkboxes.values():
                checkbox.set_active(True)

        def _on_deselect_all_clicked(self, _button):
            for checkbox in self._title_checkboxes.values():
                checkbox.set_active(False)

        def _get_selected_titles(self):
            """Return list of selected title rows."""
            selected = []
            for index, checkbox in self._title_checkboxes.items():
                if checkbox.get_active() and index < len(self._rows):
                    selected.append(self._rows[index])
            return selected

        def _on_show_conversion_list_clicked(self, _button):
            selected = self._get_selected_titles()
            text = _format_conversion_list(selected)
            self.text_view.get_buffer().set_text(text)
            sel_count = len(selected)
            self.status_label.set_text(
                f"Conversion list showing {sel_count} title{'s' if sel_count != 1 else ''}"
            )

        def _on_copy_files_clicked(self, _button):
            """Launch copy dialog for first selected title's first recording."""
            selected = self._get_selected_titles()
            if not selected:
                self.status_label.set_text("Error: No titles selected")
                return

            first_selected = selected[0]
            recordings = first_selected.get("recordings", [])
            if not recordings:
                self.status_label.set_text("Error: No recordings in selected title")
                return

            src_file = recordings[0].get("filename")
            if not src_file:
                self.status_label.set_text("Error: No valid source file")
                return

            try:
                import tempfile

                tmpdir = tempfile.gettempdir()
                dst_file = str(Path(tmpdir) / Path(src_file).name)
                dialog = FileCopyProgressDialog(
                    self.get_application(), src_file, dst_file
                )
                dialog.present()
            except Exception as e:
                errorNotify(sys.exc_info()[2], e)
                self.status_label.set_text(f"Error: {e}")

        def _populate_title_list(self):
            while True:
                row = self.title_list.get_row_at_index(0)
                if row is None:
                    break
                self.title_list.remove(row)

            self._title_checkboxes = {}

            for index, row_data in enumerate(self._rows):
                row = Gtk.ListBoxRow()
                row.set_selectable(True)
                row.set_activatable(True)
                row._title_index = index

                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                hbox.set_margin_top(6)
                hbox.set_margin_bottom(6)
                hbox.set_margin_start(8)
                hbox.set_margin_end(8)

                checkbox = Gtk.CheckButton()
                checkbox.set_active(False)
                self._title_checkboxes[index] = checkbox
                hbox.append(checkbox)

                label = Gtk.Label(label=f"{row_data['display']} ({row_data['count']})")
                label.set_xalign(0)
                label.set_hexpand(True)
                hbox.append(label)

                row.set_child(hbox)
                self.title_list.append(row)

            if self._rows:
                first = self.title_list.get_row_at_index(0)
                self.title_list.select_row(first)

        def _on_title_selected(self, _listbox, row):
            if row is None:
                return
            row_index = getattr(row, "_title_index", None)
            if row_index is None or row_index >= len(self._rows):
                return

            row_data = self._rows[row_index]
            text = _format_title_details(row_data["title"], row_data["recordings"])
            self.text_view.get_buffer().set_text(text)

        def refresh_data(self):
            """Load filteredTitles() and render an interactive split view."""
            try:
                recs, titles = filteredTitles()
                self._rows = _build_title_rows(titles)
                self._populate_title_list()

                if not self._rows:
                    self.text_view.get_buffer().set_text(
                        _format_filtered_titles(recs, titles)
                    )

                msg = f"Loaded {len(recs)} recordings across {len(self._rows)} title(s)"
                self.status_label.set_text(msg)
            except Exception as e:
                errorNotify(sys.exc_info()[2], e)
                self._rows = []
                self.text_view.get_buffer().set_text(
                    f"Error loading filteredTitles():\n\n{e}\n"
                )
                self.status_label.set_text("Failed to load recordings")

    class FilteredTitlesApp(Gtk.Application):
        """GTK4 Application wrapper."""

        def __init__(self):
            super().__init__(application_id="uk.co.tstomkv.filteredtitles")

        def do_activate(self):
            window = self.props.active_window
            if window is None:
                window = FilteredTitlesWindow(self)
            window.present()


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
