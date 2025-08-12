
import time
import subprocess
from .database import record_activity, update_activity_end_time


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
    except (subprocess.CalledProcessError, ValueError):
        return "Unknown", "Unknown"

def start_tracking():
    """Starts tracking active application and window title, recording to the database."""
    current_app_name = None
    current_window_title = None
    activity_id = None

    print("Starting activity tracking... Press Ctrl+C to stop.")

    try:
        while True:
            app_name, window_title = get_active_window_info()

            if app_name != current_app_name or window_title != current_window_title:
                if activity_id:
                    update_activity_end_time(activity_id)

                activity_id = record_activity(app_name, window_title)
                current_app_name = app_name
                current_window_title = window_title
                print(f"Tracking: App='{app_name}', Window='{window_title}'")

            time.sleep(1)  # Check every second
    except KeyboardInterrupt:
        if activity_id:
            update_activity_end_time(activity_id)
        print("Tracking stopped.")

