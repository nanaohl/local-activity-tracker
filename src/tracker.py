import os
import re
import signal
import time
import subprocess
import sys
from .database import DATABASE_NAME, record_activity, update_activity_end_time

# Written while tracking so other processes (e.g. the web UI) can see and stop the tracker.
PID_FILE = os.path.join(os.path.dirname(DATABASE_NAME), "tracker.pid")

# Seconds without keyboard/mouse input before time counts as idle.
IDLE_THRESHOLD = 60

BROWSER_URL_SCRIPTS = {
    "Safari": 'tell application "Safari" to get URL of front document',
}
for _chromium in ("Google Chrome", "Arc", "Helium", "Brave Browser", "Microsoft Edge", "Chromium", "Vivaldi"):
    BROWSER_URL_SCRIPTS[_chromium] = (
        f'tell application "{_chromium}" to get URL of active tab of front window'
    )


def get_active_window_info():
    """Returns the active application name and its window title on macOS."""
    try:
        script = """
        tell application "System Events"
            set frontApp to first application process whose frontmost is true
            set frontAppName to name of frontApp
            tell process frontAppName
                try
                    set windowTitle to name of window 1
                on error
                    set windowTitle to ""
                end try
            end tell
        end tell
        return {frontAppName, windowTitle}
        """
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, check=True
        )
        app_name, window_title = result.stdout.strip().split(", ", 1)
        return app_name, window_title
    except subprocess.CalledProcessError as e:
        _log_once(e.stderr.strip())
        return "Unknown", "Unknown"
    except ValueError:
        return "Unknown", "Unknown"


_logged_errors = set()


def _log_once(message):
    """Writes an error to stderr the first time it occurs (e.g. missing Accessibility permission)."""
    if message and message not in _logged_errors:
        _logged_errors.add(message)
        print(f"osascript error: {message}", file=sys.stderr)


def get_browser_url(app_name):
    """Returns the URL of the active tab if the app is a supported browser."""
    script = BROWSER_URL_SCRIPTS.get(app_name)
    if not script:
        return None
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, check=True, timeout=2
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def get_idle_seconds():
    """Returns seconds since the last keyboard/mouse input."""
    try:
        result = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True, check=True
        )
        match = re.search(r'"HIDIdleTime" = (\d+)', result.stdout)
        return int(match.group(1)) / 1e9 if match else 0
    except subprocess.CalledProcessError:
        return 0


def running_tracker_pid():
    """Returns the pid of an already-running tracker, or None."""
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return None


def _raise_keyboard_interrupt(signum, frame):
    raise KeyboardInterrupt


def start_tracking():
    """Starts tracking active application and window title, recording to the database."""
    current = None
    activity_id = None
    idle_seconds = 0.0

    existing_pid = running_tracker_pid()
    if existing_pid is not None and existing_pid != os.getpid():
        print(f"Tracking is already running (pid {existing_pid}).")
        return

    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    print("Starting activity tracking... Press Ctrl+C to stop.")

    last_tick = time.monotonic()
    try:
        while True:
            app_name, window_title = get_active_window_info()
            url = get_browser_url(app_name)

            now = time.monotonic()
            if activity_id and get_idle_seconds() >= IDLE_THRESHOLD:
                idle_seconds += now - last_tick
            last_tick = now

            if (app_name, window_title, url) != current:
                if activity_id:
                    update_activity_end_time(activity_id, idle_seconds)

                activity_id = record_activity(app_name, window_title, url)
                idle_seconds = 0.0
                current = (app_name, window_title, url)
                print(f"Tracking: App='{app_name}', Window='{window_title}'")

            time.sleep(1)  # Check every second
    except KeyboardInterrupt:
        if activity_id:
            update_activity_end_time(activity_id, idle_seconds)
        print("Tracking stopped.")
    finally:
        try:
            os.remove(PID_FILE)
        except FileNotFoundError:
            pass
