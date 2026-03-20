"""Transfer helpers and copy progress dialog for the GTK4 UI."""

import hashlib
import os
import subprocess
import threading
import time
from pathlib import Path

from .ffmpeg import convert_ts_to_mkv, videoDuration
from .files import getFile, humanSize, remoteCommand, remoteFileSize, sendFile
from .gtk4_runtime import GLib, Gtk
from .tvh import fileMoved


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


def _parse_stats_content(content):
    """Parse ffmpeg key=value progress content into a dict."""
    stats = {}
    for line in content.splitlines():
        if "=" not in line:
            continue
        key, value = line.strip().split("=", 1)
        stats[key] = value
    return stats


def _read_stats_file(statsfile):
    """Read and parse a ffmpeg stats file, returning an empty dict on error."""
    try:
        path = Path(statsfile)
        if not path.exists():
            return {}
        return _parse_stats_content(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def _stats_elapsed_seconds(stats, fallback=0.0):
    """Extract elapsed seconds from ffmpeg stats data."""
    for key in ("out_time_ms", "out_time_us"):
        raw = stats.get(key)
        if raw and raw != "N/A":
            try:
                return int(raw) / 1_000_000
            except ValueError:
                continue
    return fallback


def _conversion_progress_fraction(elapsed_seconds, duration_seconds):
    """Return conversion fraction as a value between 0.0 and 1.0."""
    if duration_seconds and duration_seconds > 0:
        return min(1.0, max(0.0, elapsed_seconds / duration_seconds))
    return 0.0


def _format_conversion_status(filename, elapsed_seconds, duration_seconds, speed):
    """Format conversion status text for the hybrid progress dialog."""
    elapsed_txt = _format_elapsed_mmss(elapsed_seconds)
    speed_txt = speed if speed else "N/A"

    if duration_seconds and duration_seconds > 0:
        duration_txt = _format_elapsed_mmss(duration_seconds)
        pct = _conversion_progress_fraction(elapsed_seconds, duration_seconds) * 100.0
        return (
            f"Converting {filename}: {pct:.1f}% "
            f"({elapsed_txt}/{duration_txt}) speed {speed_txt}"
        )

    return f"Converting {filename}: elapsed {elapsed_txt} speed {speed_txt}"


def _publish_converted_output(remote_src, local_mkv, progress_callback=None):
    """Publish converted MKV back to media server and notify tvheadend.

    Steps:
    1. Upload local mkv to the same remote directory as source.
    2. Notify tvheadend with fileMoved(src, dst).
    3. Delete original remote source file.
    """

    def _emit(status, step_fraction):
        if progress_callback is not None:
            progress_callback(status, step_fraction)

    remote_dst = str(Path(remote_src).with_suffix(".mkv"))
    mkv_name = Path(remote_dst).name

    _emit(f"Publishing {mkv_name}: uploading", 0.20)
    if not sendFile(local_mkv, remote_dst, banner=False):
        _emit(f"Failed to upload {mkv_name} to media server", 0.0)
        return False, f"Failed to upload {mkv_name} to media server"

    _emit(f"Publishing {mkv_name}: verifying checksum", 0.45)
    local_sha = _local_file_sha256(local_mkv)
    remote_sha = _remote_file_sha256(remote_dst)
    if not local_sha or not remote_sha:
        remoteCommand(f'rm -f "{remote_dst}"')
        _emit(f"Uploaded {mkv_name}, but checksum verification failed", 0.0)
        return False, f"Uploaded {mkv_name}, but checksum verification failed"

    if local_sha != remote_sha:
        remoteCommand(f'rm -f "{remote_dst}"')
        _emit(f"Uploaded {mkv_name}, but checksum mismatch", 0.0)
        return False, f"Uploaded {mkv_name}, but checksum mismatch"

    _emit(f"Publishing {mkv_name}: notifying tvheadend", 0.70)
    try:
        fileMoved(remote_src, remote_dst)
    except Exception as e:
        _emit(f"Uploaded {mkv_name}, but tvheadend notify failed: {e}", 0.0)
        return False, f"Uploaded {mkv_name}, but tvheadend notify failed: {e}"

    _emit(f"Publishing {mkv_name}: deleting source .ts", 0.90)
    delete_out = remoteCommand(f'rm -f "{remote_src}" && echo __deleted__')
    if "__deleted__" not in delete_out:
        _emit(f"Uploaded {mkv_name}, but failed to delete source file", 0.0)
        return False, f"Uploaded {mkv_name}, but failed to delete source file"

    _emit(f"Published {mkv_name} to media server", 1.0)
    return True, f"Published {mkv_name} to media server"


def _desktop_notify(title, body):
    """Send a desktop notification, preferring Gio and falling back to notify-send."""
    if Gtk is not None:
        try:
            from gi.repository import Gio

            app = Gio.Application.get_default()
            if app is not None:
                notification = Gio.Notification.new(title)
                notification.set_body(body)
                app.send_notification(None, notification)
                return True
        except Exception:
            pass

    try:
        result = subprocess.run(
            ["notify-send", title, body],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


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
        """GTK4 hybrid progress dialog for copying and converting files."""

        def __init__(self, application, file_pairs):
            super().__init__(application=application)
            self.set_title("Copying and Converting Files")
            self.set_default_size(550, 250)
            self.set_modal(True)
            self.file_pairs = file_pairs  # List of (src, dst) tuples
            self.current_index = 0
            self._cancelled = False
            self._finished = False
            self._conversion_finished = False
            self.total_size = 0  # Total bytes to copy
            self.total_bytes_transferred = 0  # Cumulative bytes transferred
            self._overall_start_time = time.monotonic()
            self.total_conversions = 0
            self.completed_conversions = 0
            self.total_publishes = 0
            self.completed_publishes = 0

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

            self.conversion_label = Gtk.Label(label="Conversion: pending")
            self.conversion_label.set_xalign(0)
            box.append(self.conversion_label)

            self.publish_label = Gtk.Label(label="Publish: pending")
            self.publish_label.set_xalign(0)
            box.append(self.publish_label)

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

        def _notify_workflow_complete(self, summary_text):
            """Trigger a GNOME desktop notification for completed workflow."""

            def _notify():
                _desktop_notify("tstomkv conversion complete", summary_text)
                return False

            if GLib is not None:
                GLib.idle_add(_notify)
            else:
                _notify()

        def _set_overall_label(self, overall_bytes=None):
            """Render overall bytes progress and total elapsed time."""
            if overall_bytes is None:
                overall_bytes = self.total_bytes_transferred

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

        def _on_copy_progress(self, progress, status, overall_bytes, finished=False):
            def _update_ui():
                self.progress_bar.set_fraction(progress)
                self.status_label.set_text(status)
                self._set_overall_label(overall_bytes)
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

        def _on_conversion_progress(self, progress, status, overall_fraction):
            def _update_ui():
                self.progress_bar.set_fraction(progress)
                self.status_label.set_text(status)
                self._set_overall_label(self.total_bytes_transferred)
                self.conversion_label.set_text(
                    f"Conversion: {self.completed_conversions}/{self.total_conversions} files complete ({overall_fraction * 100:.1f}%)"
                )

            if GLib is not None:
                GLib.idle_add(_update_ui)

        def _on_publish_progress(self, status, step_fraction, overall_fraction):
            def _update_ui():
                self.progress_bar.set_fraction(step_fraction)
                self.status_label.set_text(status)
                self._set_overall_label(self.total_bytes_transferred)
                self.publish_label.set_text(
                    f"Publish: {self.completed_publishes}/{self.total_publishes} files complete ({overall_fraction * 100:.1f}%)"
                )

            if GLib is not None:
                GLib.idle_add(_update_ui)

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

        def _monitor_conversion_progress(self, src_path, statsfile, duration_seconds):
            """Monitor ffmpeg progress stats for a single conversion."""
            last_elapsed = 0.0
            src_name = Path(src_path).name
            while not self._conversion_finished and not self._cancelled:
                stats = _read_stats_file(statsfile)
                elapsed = _stats_elapsed_seconds(stats, fallback=last_elapsed)
                last_elapsed = elapsed
                speed = stats.get("speed", "N/A")
                progress = _conversion_progress_fraction(elapsed, duration_seconds)
                if stats.get("progress") == "end":
                    progress = 1.0

                overall_fraction = (
                    (self.completed_conversions + progress) / self.total_conversions
                    if self.total_conversions > 0
                    else 0.0
                )
                status = _format_conversion_status(
                    src_name, elapsed, duration_seconds, speed
                )
                self._on_conversion_progress(progress, status, overall_fraction)

                if stats.get("progress") == "end":
                    break
                time.sleep(1)

        def _convert_single_file(self, ts_path, mkv_path, statsfile):
            """Run conversion worker for one ts file."""
            convert_ts_to_mkv(ts_path, mkv_path, statsfile, overwrite=True)

        def _convert_all_files(self, copied_files):
            """Convert copied ts files one at a time with concurrent progress monitor."""
            convert_candidates = [
                (remote_src, local_ts)
                for remote_src, local_ts in copied_files
                if str(local_ts).lower().endswith(".ts")
            ]
            self.total_conversions = len(convert_candidates)
            self.completed_conversions = 0
            self.total_publishes = len(convert_candidates)
            self.completed_publishes = 0

            if self.total_conversions == 0:
                self._on_conversion_progress(1.0, "No .ts files to convert", 1.0)
                self._on_publish_progress("No files to publish", 1.0, 1.0)
                return 0

            for index, (remote_src, ts_path) in enumerate(convert_candidates):
                if self._cancelled:
                    break

                ts_name = Path(ts_path).name
                mkv_path = str(Path(ts_path).with_suffix(".mkv"))
                statsfile = f"{ts_path}-transcode.stats"

                try:
                    stats_path = Path(statsfile)
                    if stats_path.exists():
                        stats_path.unlink()
                except Exception:
                    pass

                def _update_file_label():
                    self.file_label.set_text(
                        f"Converting: {ts_name} ({index + 1}/{self.total_conversions})"
                    )

                if GLib is not None:
                    GLib.idle_add(_update_file_label)

                duration_seconds = videoDuration(ts_path) or 0
                self._conversion_finished = False

                convert_thread = threading.Thread(
                    target=self._convert_single_file,
                    args=(ts_path, mkv_path, statsfile),
                    daemon=True,
                )
                monitor_thread = threading.Thread(
                    target=self._monitor_conversion_progress,
                    args=(ts_path, statsfile, duration_seconds),
                    daemon=True,
                )

                convert_thread.start()
                monitor_thread.start()

                convert_thread.join()
                self._conversion_finished = True
                monitor_thread.join(timeout=10)

                if not Path(mkv_path).exists():
                    overall_fraction = (
                        self.completed_conversions / self.total_conversions
                        if self.total_conversions > 0
                        else 0.0
                    )
                    self._on_conversion_progress(
                        0.0,
                        f"Conversion failed for {ts_name}",
                        overall_fraction,
                    )
                    publish_overall = (
                        self.completed_publishes / self.total_publishes
                        if self.total_publishes > 0
                        else 0.0
                    )
                    self._on_publish_progress(
                        f"Publish skipped for {ts_name}: conversion failed",
                        0.0,
                        publish_overall,
                    )
                    continue

                def _publish_callback(step_status, step_fraction):
                    publish_overall = (
                        (self.completed_publishes + step_fraction)
                        / self.total_publishes
                        if self.total_publishes > 0
                        else 0.0
                    )
                    self._on_publish_progress(
                        step_status,
                        step_fraction,
                        publish_overall,
                    )

                publish_ok, publish_msg = _publish_converted_output(
                    remote_src,
                    mkv_path,
                    progress_callback=_publish_callback,
                )
                if not publish_ok:
                    overall_fraction = (
                        self.completed_conversions / self.total_conversions
                        if self.total_conversions > 0
                        else 0.0
                    )
                    self._on_conversion_progress(0.0, publish_msg, overall_fraction)
                    continue

                self.completed_conversions += 1
                self.completed_publishes += 1
                overall_fraction = (
                    self.completed_conversions / self.total_conversions
                    if self.total_conversions > 0
                    else 0.0
                )
                self._on_conversion_progress(
                    1.0,
                    publish_msg,
                    overall_fraction,
                )
                publish_overall = (
                    self.completed_publishes / self.total_publishes
                    if self.total_publishes > 0
                    else 0.0
                )
                self._on_publish_progress(publish_msg, 1.0, publish_overall)

            return self.completed_conversions

        def _copy_all_files(self):
            """Copy all files, then convert them sequentially."""
            try:
                self.total_size = self._calculate_total_size()
                if self.total_size <= 0:
                    self._on_copy_error("Could not determine total size of files")
                    return

                copied_local_files = []

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
                        copied_local_files.append((src, dst))
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
                        copied_local_files.append((src, dst))

                    if not success:
                        if not self._cancelled:
                            self._on_copy_error(f"Failed to copy {src}")
                        continue

                    self.current_index = index + 1

                if not self._cancelled:
                    converted_count = self._convert_all_files(copied_local_files)
                    size_str = humanSize(self.total_bytes_transferred)
                    summary_text = (
                        f"Copy+convert complete: {len(copied_local_files)} file(s) copied "
                        f"({size_str}), {converted_count} conversion(s) complete"
                    )
                    self._on_copy_progress(
                        1.0,
                        summary_text,
                        self.total_bytes_transferred,
                        finished=True,
                    )
                    self._notify_workflow_complete(summary_text)
                else:
                    self._on_copy_progress(
                        1.0,
                        "Operation cancelled",
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
