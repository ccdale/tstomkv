"""GTK4 application windows for filtered titles browsing."""

import sys
from pathlib import Path

import tstomkv
from tstomkv import errorNotify
from tstomkv.recordings import filteredTitles

from .gtk4_formatting import (
    _build_title_rows,
    _format_conversion_list,
    _format_filtered_titles,
    _format_title_details,
)
from .gtk4_runtime import Gtk
from .gtk4_transfer import FileCopyProgressDialog

FilteredTitlesWindow = None
FilteredTitlesApp = None
_APP_ICON_NAME = "tstomkv-icon"


def _icon_asset_dirs():
    """Return existing directories that may contain app icon assets."""
    dirs = []
    package_assets = Path(__file__).resolve().parent / "assets"
    for path in (package_assets / "png", package_assets):
        if path.exists() and path not in dirs:
            dirs.append(path)

    try:
        repo_root = Path(tstomkv.gitroot())
    except SystemExit:
        repo_root = None

    if repo_root is not None:
        repo_assets = repo_root / "assets"
        for path in (repo_assets / "png", repo_assets):
            if path.exists() and path not in dirs:
                dirs.append(path)

    return dirs


def _icon_file_candidates():
    """Return icon files in order of preference for in-app display."""
    candidates = []
    for asset_dir in _icon_asset_dirs():
        names = []
        if asset_dir.name == "png":
            names.extend(
                [
                    f"{_APP_ICON_NAME}-256.png",
                    f"{_APP_ICON_NAME}-512.png",
                    f"{_APP_ICON_NAME}.png",
                ]
            )
        else:
            names.extend([f"{_APP_ICON_NAME}.svg", f"{_APP_ICON_NAME}.png"])
        for name in names:
            path = asset_dir / name
            if path.exists() and path not in candidates:
                candidates.append(path)
    return candidates


def _resolve_icon_file():
    """Return the preferred icon file path, if any."""
    candidates = _icon_file_candidates()
    if candidates:
        return candidates[0]
    return None


if Gtk is not None:

    def _register_app_icon(window):
        """Register local icon search paths and apply the icon name to the window."""
        display = window.get_display()
        if display is None:
            return

        icon_theme = Gtk.IconTheme.get_for_display(display)
        existing = set(icon_theme.get_search_path())
        for asset_dir in _icon_asset_dirs():
            asset_dir_str = str(asset_dir)
            if asset_dir_str not in existing:
                icon_theme.add_search_path(asset_dir_str)

        Gtk.Window.set_default_icon_name(_APP_ICON_NAME)
        window.set_icon_name(_APP_ICON_NAME)

    def _build_header_title_widget():
        """Create a title widget with the app icon for the header bar."""
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon_path = _resolve_icon_file()
        if icon_path is not None:
            image = Gtk.Image.new_from_file(str(icon_path))
            image.set_pixel_size(24)
            title_box.append(image)

        label = Gtk.Label(label="tstomkv GTK4")
        title_box.append(label)
        return title_box

    class FilteredTitlesWindow(Gtk.ApplicationWindow):
        """Main GTK4 window for displaying filtered titles."""

        def __init__(self, application):
            super().__init__(application=application)
            self.set_title(f"tstomkv GTK4 - {tstomkv.getVersion()}")
            self.set_default_size(980, 700)
            self._rows = []
            self._title_checkboxes = {}

            try:
                _register_app_icon(self)
            except Exception as e:
                errorNotify(sys.exc_info()[2], e)

            header_bar = Gtk.HeaderBar()
            header_bar.set_title_widget(_build_header_title_widget())
            self.set_titlebar(header_bar)

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

            copy_btn = Gtk.Button(label="Copy && Convert Files")
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
            """Launch copy dialog for all files in selected titles."""
            selected = self._get_selected_titles()
            if not selected:
                self.status_label.set_text("Error: No titles selected")
                return

            file_pairs = []
            for title_row in selected:
                recordings = title_row.get("recordings", [])
                for rec in recordings:
                    src_file = rec.get("filename")
                    if not src_file:
                        continue

                    try:
                        import tempfile

                        tmpdir = tempfile.gettempdir()
                        dst_file = str(Path(tmpdir) / Path(src_file).name)
                        file_pairs.append((src_file, dst_file))
                    except Exception as e:
                        errorNotify(sys.exc_info()[2], e)

            if not file_pairs:
                self.status_label.set_text("Error: No valid files to copy")
                return

            try:
                dialog = FileCopyProgressDialog(self.get_application(), file_pairs)
                dialog.present()
                self.status_label.set_text(
                    f"Copying and converting {len(file_pairs)} file{'s' if len(file_pairs) != 1 else ''}..."
                )
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
