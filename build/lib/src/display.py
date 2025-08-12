
from tabulate import tabulate
from datetime import timedelta

def format_duration(seconds):
    """Formats duration in seconds to HH:MM:SS."""
    return str(timedelta(seconds=int(seconds)))

def display_summary(summary, view_type):
    """Displays the activity summary in a formatted table."""
    if not summary:
        print(f"No data available for the {view_type} view.")
        return

    headers = ["Application", "Window/Tab", "Time Spent"]
    table_data = []

    for app_name, window_title, duration in summary:
        table_data.append([app_name, window_title, format_duration(duration)])

    print(f"\n--- Activity Summary ({view_type.capitalize()}) ---")
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
