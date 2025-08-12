
import time
from AppKit import NSWorkspace
from .database import record_activity, update_activity_end_time

def get_active_window_info():
    """Returns the active application name and its window title on macOS."""
    active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
    app_name = active_app.localizedName()

    window_title = "Unknown"
    # This part is tricky as direct access to window titles of other apps is restricted
    # without Accessibility permissions. For a simple CLI, we might not have them.
    # We'll try to get the window title from the active application if possible.
    # A more robust solution would involve AppleScript or Accessibility APIs.
    # For now, we'll just return the app name and a generic "Unknown" title.
    # If the user grants Accessibility permissions, more advanced methods could be used.

    # Attempt to get window title using a less intrusive method (might not always work)
    # This is a placeholder and might need refinement or user interaction for permissions.
    try:
        # This is a simplified attempt. Real-world window title fetching is complex.
        # It often requires UI scripting or Accessibility API, which need user permissions.
        # For a basic CLI, we'll rely on the app name primarily.
        pass # No direct window title fetching for now to avoid permission issues
    except Exception:
        pass

    return app_name, window_title

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

