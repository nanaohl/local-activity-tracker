
import sqlite3
from datetime import datetime

DATABASE_NAME = "activity.db"

def create_table():
    """Creates the activity table in the database if it doesn't exist."""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT NOT NULL,
            window_title TEXT,
            start_time DATETIME NOT NULL,
            end_time DATETIME,
            day INTEGER NOT NULL,
            week INTEGER NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

def record_activity(app_name, window_title):
    """Records a new activity in the database."""
    create_table()
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    now = datetime.now()
    c.execute(
        """
        INSERT INTO activity (app_name, window_title, start_time, day, week, month, year)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            app_name,
            window_title,
            now,
            now.day,
            now.isocalendar()[1],
            now.month,
            now.year,
        ),
    )
    conn.commit()
    activity_id = c.lastrowid
    conn.close()
    return activity_id

def update_activity_end_time(activity_id):
    """Updates the end_time of an activity."""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute(
        """
        UPDATE activity
        SET end_time = ?
        WHERE id = ?
        """,
        (datetime.now(), activity_id),
    )
    conn.commit()
    conn.close()

def get_daily_summary(day, month, year):
    """Retrieves the daily activity summary from the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute(
        """
        SELECT app_name, window_title, SUM(strftime('%s', end_time) - strftime('%s', start_time)) as duration
        FROM activity
        WHERE day = ? AND month = ? AND year = ? AND end_time IS NOT NULL
        GROUP BY app_name, window_title
        ORDER BY duration DESC
        """,
        (day, month, year),
    )
    summary = c.fetchall()
    conn.close()
    return summary

def get_weekly_summary(week, year):
    """Retrieves the weekly activity summary from the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute(
        """
        SELECT app_name, window_title, SUM(strftime('%s', end_time) - strftime('%s', start_time)) as duration
        FROM activity
        WHERE week = ? AND year = ? AND end_time IS NOT NULL
        GROUP BY app_name, window_title
        ORDER BY duration DESC
        """,
        (week, year),
    )
    summary = c.fetchall()
    conn.close()
    return summary

def get_monthly_summary(month, year):
    """Retrieves the monthly activity summary from the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute(
        """
        SELECT app_name, window_title, SUM(strftime('%s', end_time) - strftime('%s', start_time)) as duration
        FROM activity
        WHERE month = ? AND year = ? AND end_time IS NOT NULL
        GROUP BY app_name, window_title
        ORDER BY duration DESC
        """,
        (month, year),
    )
    summary = c.fetchall()
    conn.close()
    return summary

def get_yearly_summary(year):
    """Retrieve the yearly activity summary from the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute(
        """
        SELECT app_name, window_title, SUM(strftime('%s', end_time) - strftime('%s', start_time)) as duration
        FROM activity
        WHERE year = ? AND end_time IS NOT NULL
        GROUP BY app_name, window_title
        ORDER BY duration DESC
        """,
        (year,),
    )
    summary = c.fetchall()
    conn.close()
    return summary
