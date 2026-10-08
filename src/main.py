
import argparse
import subprocess
import sys
import os
from datetime import datetime
from .database import (
    create_table,
    get_daily_summary,
    get_weekly_summary,
    get_monthly_summary,
    get_yearly_summary,
)
from .tracker import start_tracking
from .display import display_summary
from . import autostart, bundle

def start_web_server():
    # Get the absolute path to the directory where this script is located
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    # Define the absolute path for the web server script
    web_server_script = os.path.join(SRC_DIR, "web", "server.py")
    print(f"Starting web server at http://127.0.0.1:5001")
    try:
        subprocess.run([sys.executable, web_server_script], check=True)
    except FileNotFoundError:
        print(f"Error: Could not find {web_server_script}. Make sure the file exists.")
    except subprocess.CalledProcessError as e:
        print(f"Error starting web server: {e}")

def main():
    create_table()  # Ensure table exists when the app starts

    parser = argparse.ArgumentParser(description="Track application usage and display summaries.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Track command
    track_parser = subparsers.add_parser("track", help="Start tracking application usage.")

    # Daily summary command
    daily_parser = subparsers.add_parser("daily", help="Show daily activity summary.")
    daily_parser.add_argument(
        "--day", type=int, default=datetime.now().day, help="Day (1-31)"
    )
    daily_parser.add_argument(
        "--month", type=int, default=datetime.now().month, help="Month (1-12)"
    )
    daily_parser.add_argument(
        "--year", type=int, default=datetime.now().year, help="Year"
    )

    # Weekly summary command
    weekly_parser = subparsers.add_parser("weekly", help="Show weekly activity summary.")
    weekly_parser.add_argument(
        "--week",
        type=int,
        default=datetime.now().isocalendar()[1],
        help="Week number (1-52)",
    )
    weekly_parser.add_argument(
        "--year", type=int, default=datetime.now().year, help="Year"
    )

    # Monthly summary command
    monthly_parser = subparsers.add_parser("monthly", help="Show monthly activity summary.")
    monthly_parser.add_argument(
        "--month", type=int, default=datetime.now().month, help="Month (1-12)"
    )
    monthly_parser.add_argument(
        "--year", type=int, default=datetime.now().year, help="Year"
    )

    # Yearly summary command
    yearly_parser = subparsers.add_parser("yearly", help="Show yearly activity summary.")
    yearly_parser.add_argument(
        "--year", type=int, default=datetime.now().year, help="Year"
    )

    # Web command
    web_parser = subparsers.add_parser("web", help="Start the web server to view activity.")

    # App command
    app_parser = subparsers.add_parser(
        "app", help="Run the Mac app window, or install it in ~/Applications."
    )
    app_parser.add_argument(
        "action", nargs="?", default="run", choices=["run", "install", "uninstall", "status"]
    )

    # Autostart command
    autostart_parser = subparsers.add_parser(
        "autostart", help="Start tracking and the web UI automatically at login."
    )
    autostart_parser.add_argument("action", choices=["install", "uninstall", "status"])

    args = parser.parse_args()

    if args.command == "track":
        start_tracking()
    elif args.command == "daily":
        summary = get_daily_summary(args.day, args.month, args.year)
        display_summary(summary, "daily")
    elif args.command == "weekly":
        summary = get_weekly_summary(args.week, args.year)
        display_summary(summary, "weekly")
    elif args.command == "monthly":
        summary = get_monthly_summary(args.month, args.year)
        display_summary(summary, "monthly")
    elif args.command == "yearly":
        summary = get_yearly_summary(args.year)
        display_summary(summary, "yearly")
    elif args.command == "web":
        start_web_server()
    elif args.command == "app":
        if args.action == "run":
            from .app import main as run_app
            run_app()
        else:
            getattr(bundle, args.action)()
    elif args.command == "autostart":
        getattr(autostart, args.action)()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
