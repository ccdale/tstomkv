"""Shared GTK4 runtime imports."""

try:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk
except (ImportError, ValueError):
    GLib = None
    Gtk = None
