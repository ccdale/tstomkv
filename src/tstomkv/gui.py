import sys
import tkinter as tk
from tkinter import ttk

import tstomkv
from tstomkv import errorNotify
from tstomkv.recordings import filteredTitles


class CheckboxListbox(tk.Frame):
    """A listbox widget with checkboxes for each item."""

    def __init__(self, parent, items=None, **kwargs):
        super().__init__(parent, **kwargs)

        # Create the main frame
        self.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create scrollable frame
        self.canvas = tk.Canvas(self)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.canvas)

        # Configure scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Pack the canvas and scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Store checkbox variables and items
        self.checkbox_vars = []
        self.items = items or []

        # Create checkboxes for initial items
        self.update_items(self.items)

        # Bind mousewheel to canvas
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def update_items(self, items):
        """Update the listbox with new items."""
        # Clear existing checkboxes
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.checkbox_vars = []
        self.items = items

        # Create new checkboxes
        for i, item in enumerate(items):
            var = tk.BooleanVar()
            self.checkbox_vars.append(var)

            # Create checkbox with item text
            checkbox = ttk.Checkbutton(
                self.scrollable_frame, text=str(item), variable=var, padding=(5, 2)
            )
            checkbox.pack(fill=tk.X, anchor="w")

    def get_selected_items(self):
        """Return a list of selected items."""
        selected = []
        for i, var in enumerate(self.checkbox_vars):
            if var.get():
                selected.append(self.items[i])
        return selected

    def get_selected_indices(self):
        """Return a list of selected item indices."""
        selected_indices = []
        for i, var in enumerate(self.checkbox_vars):
            if var.get():
                selected_indices.append(i)
        return selected_indices

    def select_all(self):
        """Select all items."""
        for var in self.checkbox_vars:
            var.set(True)

    def deselect_all(self):
        """Deselect all items."""
        for var in self.checkbox_vars:
            var.set(False)

    def toggle_all(self):
        """Toggle all selections."""
        for var in self.checkbox_vars:
            var.set(not var.get())


class TStoMKVGUI:
    """Main GUI application for tstomkv."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"TS to MKV Converter - {tstomkv.getVersion()}")
        self.root.geometry("800x600")

        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title label
        title_label = ttk.Label(
            main_frame, text="Select recordings to convert:", font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.pack(pady=(10, 0))

        # Load recordings and create checkbox listbox
        self.load_recordings()

        # Create checkbox listbox
        self.checkbox_listbox = CheckboxListbox(main_frame, items=self.recording_names)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # Control buttons
        ttk.Button(
            button_frame, text="Select All", command=self.checkbox_listbox.select_all
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Deselect All",
            command=self.checkbox_listbox.deselect_all,
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame, text="Toggle All", command=self.checkbox_listbox.toggle_all
        ).pack(side=tk.LEFT, padx=5)

        # Action buttons
        ttk.Button(
            button_frame, text="Convert Selected", command=self.convert_selected
        ).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(
            button_frame, text="Refresh List", command=self.refresh_recordings
        ).pack(side=tk.RIGHT, padx=5)

    def load_recordings(self):
        """Load recordings from tstomkv."""
        try:
            self.status_label.config(text="Loading recordings...")
            self.root.update()

            recs, titles = filteredTitles()
            self.recordings = recs
            self.titles = titles

            # Create a list of recording names for display
            self.recording_names = []
            for title, recordings in titles.items():
                for rec in recordings:
                    filename = rec.get("filename", "Unknown")
                    self.recording_names.append(f"{title} - {filename}")

            self.status_label.config(
                text=f"Loaded {len(self.recording_names)} recordings"
            )

        except Exception as e:
            error_msg = f"Error loading recordings: {e}"
            self.status_label.config(text=error_msg)
            errorNotify(sys.exc_info()[2], e)
            # Fallback to example data
            self.recording_names = [
                "Example Recording 1 - /path/to/file1.ts",
                "Example Recording 2 - /path/to/file2.ts",
                "Example Recording 3 - /path/to/file3.ts",
            ]

    def refresh_recordings(self):
        """Refresh the recordings list."""
        self.load_recordings()
        self.checkbox_listbox.update_items(self.recording_names)

    def convert_selected(self):
        """Convert the selected recordings."""
        selected_items = self.checkbox_listbox.get_selected_items()
        # selected_indices = self.checkbox_listbox.get_selected_indices()

        if not selected_items:
            self.status_label.config(text="No items selected")
            return

        self.status_label.config(
            text=f"Selected {len(selected_items)} recordings for conversion"
        )

        # Here you would implement the actual conversion logic
        # For now, just print the selected items
        print("Selected recordings:")
        for item in selected_items:
            print(f"  - {item}")

    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


def main():
    """Main entry point for the GUI application."""
    try:
        app = TStoMKVGUI()
        app.run()
    except Exception as e:
        errorNotify(sys.exc_info()[2], e)
        print(f"GUI Error: {e}")


if __name__ == "__main__":
    main()
