"""Transfer helpers and copy progress dialog for the GTK4 UI."""

import hashlib
import os
import threading
import time
from pathlib import Path

from .files import getFile, humanSize, remoteCommand, remoteFileSize
from .gtk4_runtime import GLib, Gtk


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
    src_human = humanSize(src_size)
    dst_human = humanSize(dst_size)
    rate_human = humanSize(rate) if rate > 0 else "0.00 B"
    percent = (dst_size / src_size * 100) if src_size > 0 else 0.0

    return f"{filename}: {dst_human}/{src_human} ({percent:.1f}%) at {rate_human}/s"


def _format_elapsed_mmss(elapsed_seconds):
    """Format elapsed seconds as mm:ss."""
    total_seconds = max(0, int(elapsed_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _is_sha256_digest(value):
    if not value or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def _parse_sha_output(raw_value):
    if not raw_value:
        return None
    token = raw_value.strip().split()[0] if raw_value.strip() else ""
    return token.lower() if _is_sha256_digest(token.lower()) else None


def _local_file_sha256(path):
    try:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None


def _remote_file_sha256(path):
    primary = remoteCommand(f'sha256sum "{path}"')
    sha = _parse_sha_output(primary)
    if sha:
        return sha

    fallback = remoteCommand(f'shasum -a 256 "{path}"')
    return _parse_sha_output(fallback)


def _reconcile_existing_destination(src, dst):
    """Validate existing destination content before copying.

    Returns:
        Tuple of (skip_copy, status_message). If skip_copy is True, destination
        matches source and copy can be skipped. Otherwise destination is removed
        and copy should proceed.
    """
    dst_path = Path(dst)
    if not dst_path.exists():
        return False, ""

    src_sha = _remote_file_sha256(src)
    dst_sha = _local_file_sha256(dst_path)
    name = dst_path.name

    if src_sha and dst_sha and src_sha == dst_sha:
        return True, f"Skipping {name}: destination already matches source"

    try:
        dst_path.unlink()
    except Exception as e:
        raise RuntimeError(
            f"Failed to remove existing destination {dst_path}: {e}"
        ) from e

    if src_sha and dst_sha:
        return False, f"Replacing {name}: destination hash differs from source"
    return False, f"Replacing {name}: could not verify hash match"


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

            skip_copy, status = _reconcile_existing_destination(src, dst)
            if skip_copy:
                if callback:
                    callback(progress=1.0, status=status, finished=True)
                return

            start_time = time.time()
            success = getFile(src, dst, banner=False)
            if not success:
                if error_callback:
                    error_callback(f"Failed to copy {src} to {dst}")
                return

            elapsed = time.time() - start_time
            _progress, _bytes_tx, _rate = _calculate_progress(src_size, dst, elapsed)
            if callback:
                callback(progress=1.0, status="Transfer complete", finished=True)
        except Exception as e:
            if error_callback:
                error_callback(str(e))

    thread = threading.Thread(target=_do_copy, daemon=False)
    thread.start()


if Gtk is not None:

    class FileCopyProgressDialog(Gtk.ApplicationWindow):
        """GTK4 progress dialog for copying multiple files from media server."""

        def __init__(self, application, file_pairs):
            super().__init__(application=application)
            self.set_title("Copying Files from Media Server")
            self.set_default_size(550, 250)
            self.set_modal(True)
            self.file_pairs = file_pairs  # List of (src, dst) tuples
            self.current_index = 0
            self._cancelled = False
            self._finished = False
            self.total_size = 0  # Total bytes to copy
            self.total_bytes_transferred = 0  # Cumulative bytes transferred
            self._overall_start_time = time.monotonic()

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.set_margin_top(20)
            box.set_margin_bottom(20)
            box.set_margin_start(20)
            box.set_margin_end(20)

            self.file_label = Gtk.Label(label="Preparing...")
            self.file_label.set_xalign(0)
            box.append(self.file_label)

            self.status_label = Gtk.Label(label="Starting transfer...")
            self.status_label.set_xalign(0)
            self.status_label.set_wrap(True)
            box.append(self.status_label)

            self.progress_bar = Gtk.ProgressBar()
            self.progress_bar.set_fraction(0.0)
            box.append(self.progress_bar)

            self.overall_label = Gtk.Label(label="Overall: calculating...")
            self.overall_label.set_xalign(0)
            box.append(self.overall_label)

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

        def _on_copy_progress(self, progress, status, overall_bytes, finished=False):
            def _update_ui():
                self.progress_bar.set_fraction(progress)
                self.status_label.set_text(status)
                elapsed_text = _format_elapsed_mmss(
                    time.monotonic() - self._overall_start_time
                )
                if self.total_size > 0:
                    overall_human = humanSize(overall_bytes)
                    total_human = humanSize(self.total_size)
                    overall_pct = (
                        (overall_bytes / self.total_size * 100)
                        if self.total_size > 0
                        else 0.0
                    )
                    self.overall_label.set_text(
                        f"Overall: {overall_human} / {total_human} ({overall_pct:.1f}%) | Elapsed: {elapsed_text}"
                    )
                else:
                    self.overall_label.set_text(
                        f"Overall: calculating... | Elapsed: {elapsed_text}"
                    )
                if finished:
                    self._finished = True
                    self.cancel_btn.set_sensitive(False)
                    self.close_btn.set_sensitive(True)

            if GLib is not None:
                GLib.idle_add(_update_ui)

        def _on_copy_error(self, error_msg):
            def _show_error():
                self.status_label.set_text(f"Error: {error_msg}")
                self._finished = True
                self.cancel_btn.set_sensitive(False)
                self.close_btn.set_sensitive(True)

            if GLib is not None:
                GLib.idle_add(_show_error)

        def _monitor_single_progress(self, src, dst, src_size):
            """Monitor progress for a single file transfer, return bytes transferred."""
            try:
                start_time = time.time()
                while not self._finished and not self._cancelled:
                    elapsed = time.time() - start_time
                    _fraction, bytes_tx, rate = _calculate_progress(
                        src_size, dst, elapsed
                    )
                    status = _format_transfer_status(
                        Path(src).name, src_size, bytes_tx, elapsed, rate
                    )
                    overall_bytes = self.total_bytes_transferred + bytes_tx
                    overall_progress = (
                        overall_bytes / self.total_size if self.total_size > 0 else 0.0
                    )
                    self._on_copy_progress(
                        overall_progress, status, overall_bytes, finished=False
                    )
                    time.sleep(0.5)

                if Path(dst).exists():
                    return os.path.getsize(dst)
                return 0
            except Exception as e:
                self._on_copy_error(str(e))
                return 0

        def _calculate_total_size(self):
            """Calculate total size of all files to be copied."""
            total = 0
            for src, _ in self.file_pairs:
                try:
                    size = remoteFileSize(src)
                    if size > 0:
                        total += size
                except Exception:
                    pass
            return total

        def _copy_all_files(self):
            """Copy all files sequentially in background thread."""
            try:
                self.total_size = self._calculate_total_size()
                if self.total_size <= 0:
                    self._on_copy_error("Could not determine total size of files")
                    return

                for index, (src, dst) in enumerate(self.file_pairs):
                    if self._cancelled:
                        break

                    self.current_index = index

                    def _update_file_label():
                        self.file_label.set_text(
                            f"Copying: {Path(src).name} ({index + 1}/{len(self.file_pairs)})"
                        )

                    if GLib is not None:
                        GLib.idle_add(_update_file_label)

                    src_size = remoteFileSize(src)
                    if src_size < 0:
                        self._on_copy_error(f"Could not determine size for {src}")
                        continue

                    skip_copy, preflight_status = _reconcile_existing_destination(
                        src, dst
                    )
                    if skip_copy:
                        self.total_bytes_transferred += src_size
                        overall_progress = (
                            self.total_bytes_transferred / self.total_size
                            if self.total_size > 0
                            else 0.0
                        )
                        self._on_copy_progress(
                            overall_progress,
                            preflight_status,
                            self.total_bytes_transferred,
                            finished=False,
                        )
                        self.current_index = index + 1
                        continue

                    if preflight_status:
                        overall_progress = (
                            self.total_bytes_transferred / self.total_size
                            if self.total_size > 0
                            else 0.0
                        )
                        self._on_copy_progress(
                            overall_progress,
                            preflight_status,
                            self.total_bytes_transferred,
                            finished=False,
                        )

                    monitor_thread = threading.Thread(
                        target=self._monitor_single_progress,
                        args=(src, dst, src_size),
                        daemon=True,
                    )
                    monitor_thread.start()

                    success = getFile(src, dst, banner=False)
                    self._finished = True  # Signal monitor thread to exit
                    monitor_thread.join(timeout=60)
                    self._finished = False  # Reset for next iteration

                    if success and Path(dst).exists():
                        self.total_bytes_transferred += os.path.getsize(dst)

                    if not success:
                        if not self._cancelled:
                            self._on_copy_error(f"Failed to copy {src}")
                        continue

                    self.current_index = index + 1

                if not self._cancelled:
                    size_str = humanSize(self.total_bytes_transferred)
                    self._on_copy_progress(
                        1.0,
                        f"Transfer complete: {len(self.file_pairs)} files copied ({size_str})",
                        self.total_bytes_transferred,
                        finished=True,
                    )

            except Exception as e:
                self._on_copy_error(str(e))

        def _start_copy(self):
            """Start the file copy in background thread."""
            copy_thread = threading.Thread(target=self._copy_all_files, daemon=True)
            copy_thread.start()

else:

    class FileCopyProgressDialog:
        """Fallback when GTK4 is unavailable."""

        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("GTK4 unavailable")
