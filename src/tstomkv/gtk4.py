"""GTK4 app that displays the output of recordings.filteredTitles()."""

import sys

import tstomkv
from tstomkv import errorNotify
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


if Gtk is not None:

    class FilteredTitlesWindow(Gtk.ApplicationWindow):
        """Main GTK4 window for displaying filtered titles."""

        def __init__(self, application):
            super().__init__(application=application)
            self.set_title(f"tstomkv GTK4 - {tstomkv.getVersion()}")
            self.set_default_size(980, 700)
            self._rows = []

            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            outer.set_margin_top(10)
            outer.set_margin_bottom(10)
            outer.set_margin_start(10)
            outer.set_margin_end(10)

            controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            refresh_btn = Gtk.Button(label="Refresh")
            refresh_btn.connect("clicked", self._on_refresh_clicked)
            controls.append(refresh_btn)

            self.status_label = Gtk.Label(label="Ready")
            self.status_label.set_xalign(0)
            controls.append(self.status_label)
            outer.append(controls)

            split = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
            split.set_wide_handle(True)

            left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            left_label = Gtk.Label(label="Titles")
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

        def _populate_title_list(self):
            while True:
                row = self.title_list.get_row_at_index(0)
                if row is None:
                    break
                self.title_list.remove(row)

            for index, row_data in enumerate(self._rows):
                row = Gtk.ListBoxRow()
                row.set_selectable(True)
                row.set_activatable(True)
                row._title_index = index

                label = Gtk.Label(label=f"{row_data['display']} ({row_data['count']})")
                label.set_xalign(0)
                label.set_margin_top(6)
                label.set_margin_bottom(6)
                label.set_margin_start(8)
                label.set_margin_end(8)
                row.set_child(label)
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
        print("GTK4 unavailable: install PyGObject and GTK4 runtime libraries.")
        return 1

    try:
        app = FilteredTitlesApp()
        return app.run(sys.argv)
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
