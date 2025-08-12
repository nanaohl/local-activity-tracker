
import argparse
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
