
import os
import sqlite3
from datetime import datetime

# Get the absolute path to the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Define the absolute path for the database file
DATABASE_NAME = os.path.join(SCRIPT_DIR, "..", "activity.db")

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
    # Columns added after the first release; older databases are migrated in place.
    existing = {row[1] for row in c.execute("PRAGMA table_info(activity)")}
    for column, definition in (
        ("url", "TEXT"),
        ("idle_seconds", "REAL"),
        ("added", "INTEGER NOT NULL DEFAULT 0"),
        ("task_id", "TEXT"),
    ):
        if column not in existing:
            c.execute(f"ALTER TABLE activity ADD COLUMN {column} {definition}")
    # ClickUp tasks assigned to activities, cached so the timeline can show them offline.
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS clickup_task (
            id TEXT PRIMARY KEY,
            custom_id TEXT,
            name TEXT NOT NULL,
            status TEXT,
            status_color TEXT,
            url TEXT,
            list_name TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def record_activity(app_name, window_title, url=None):
    """Records a new activity in the database."""
    create_table()
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    now = datetime.now()
    c.execute(
        """
        INSERT INTO activity (app_name, window_title, url, idle_seconds, start_time, day, week, month, year)
        VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)
        """,
        (
            app_name,
            window_title,
            url,
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

def update_activity_end_time(activity_id, idle_seconds=None):
    """Updates the end_time (and optionally the idle time) of an activity."""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute(
        """
        UPDATE activity
        SET end_time = ?, idle_seconds = COALESCE(?, idle_seconds)
        WHERE id = ?
        """,
        (datetime.now(), idle_seconds, activity_id),
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

def get_activities_for_date(date_str):
    """Retrieves every raw activity row that started on a date (YYYY-MM-DD), oldest first."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT a.id, a.app_name, a.window_title, a.url, a.start_time, a.end_time, a.idle_seconds, a.added,
               a.task_id, t.custom_id AS task_custom_id, t.name AS task_name, t.status AS task_status,
               t.status_color AS task_status_color, t.url AS task_url, t.list_name AS task_list_name
        FROM activity a
        LEFT JOIN clickup_task t ON t.id = a.task_id
        WHERE date(a.start_time) = ?
        ORDER BY a.start_time, a.id
        """,
        (date_str,),
    )
    rows = [dict(row) for row in c.fetchall()]
    c.execute("SELECT MAX(id) FROM activity")
    latest_id = c.fetchone()[0]
    conn.close()
    return rows, latest_id

def delete_activities(ids):
    """Deletes activity rows by id."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.executemany("DELETE FROM activity WHERE id = ?", [(i,) for i in ids])
    conn.commit()
    conn.close()

def mark_activities_added(ids):
    """Flags activity rows as added to the timesheet."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.executemany("UPDATE activity SET added = 1 WHERE id = ?", [(i,) for i in ids])
    conn.commit()
    conn.close()

TASK_FIELDS = ("id", "custom_id", "name", "status", "status_color", "url", "list_name")


def save_tasks(tasks):
    """Inserts or refreshes cached ClickUp tasks."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.executemany(
        f"""
        INSERT INTO clickup_task ({", ".join(TASK_FIELDS)})
        VALUES ({", ".join("?" for _ in TASK_FIELDS)})
        ON CONFLICT(id) DO UPDATE SET {", ".join(f"{f} = excluded.{f}" for f in TASK_FIELDS[1:])}
        """,
        [tuple(task.get(f) for f in TASK_FIELDS) for task in tasks],
    )
    conn.commit()
    conn.close()


def refresh_known_tasks(tasks):
    """Updates cached tasks that are already assigned to activities (e.g. a changed status)."""
    conn = sqlite3.connect(DATABASE_NAME)
    known = {row[0] for row in conn.execute("SELECT id FROM clickup_task")}
    conn.close()
    save_tasks([t for t in tasks if t["id"] in known])


def assign_task(ids, task_id):
    """Assigns a ClickUp task to activity rows, or clears it when task_id is None."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.executemany("UPDATE activity SET task_id = ? WHERE id = ?", [(task_id, i) for i in ids])
    conn.commit()
    conn.close()


def get_recent_tasks(limit):
    """Tasks most recently worked on, by the latest activity assigned to them."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""
        SELECT {", ".join(f"t.{f}" for f in TASK_FIELDS)}
        FROM clickup_task t
        JOIN activity a ON a.task_id = t.id
        GROUP BY t.id
        ORDER BY MAX(a.start_time) DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def merge_activities(ids):
    """Merges activity rows into the earliest one, spanning all of their time. Returns the kept id."""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    placeholders = ",".join("?" for _ in ids)
    c.execute(
        f"""
        SELECT id, start_time, end_time, idle_seconds, added, task_id
        FROM activity WHERE id IN ({placeholders})
        ORDER BY start_time, id
        """,
        list(ids),
    )
    rows = c.fetchall()
    if len(rows) < 2:
        conn.close()
        return rows[0][0] if rows else None

    keep_id = rows[0][0]
    start_time = rows[0][1]
    end_times = [row[2] for row in rows if row[2] is not None]
    end_time = max(end_times) if end_times else None
    idle_values = [row[3] for row in rows if row[3] is not None]
    idle_seconds = sum(idle_values) if idle_values else None
    added = max(row[4] for row in rows)
    task_id = next((row[5] for row in rows if row[5]), None)

    c.execute(
        "UPDATE activity SET start_time = ?, end_time = ?, idle_seconds = ?, added = ?, task_id = ? WHERE id = ?",
        (start_time, end_time, idle_seconds, added, task_id, keep_id),
    )
    c.executemany("DELETE FROM activity WHERE id = ?", [(row[0],) for row in rows[1:]])
    conn.commit()
    conn.close()
    return keep_id

def get_activities_between(start, end):
    """Retrieves raw activity rows overlapping [start, end), oldest first."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT id, app_name, window_title, url, start_time, end_time, idle_seconds
        FROM activity
        WHERE start_time < ? AND (end_time IS NULL OR end_time > ?)
        ORDER BY start_time, id
        """,
        (str(end), str(start)),
    )
    rows = [dict(row) for row in c.fetchall()]
    c.execute("SELECT MAX(id) FROM activity")
    latest_id = c.fetchone()[0]
    conn.close()
    return rows, latest_id

def get_top_apps(limit, exclude=()):
    """Returns app names ordered by all-time tracked duration (largest first)."""
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    placeholders = ",".join("?" for _ in exclude) or "''"
    c.execute(
        f"""
        SELECT app_name
        FROM activity
        WHERE end_time IS NOT NULL AND app_name NOT IN ({placeholders})
        GROUP BY app_name
        ORDER BY SUM(strftime('%s', end_time) - strftime('%s', start_time)) DESC
        LIMIT ?
        """,
        (*exclude, limit),
    )
    apps = [row[0] for row in c.fetchall()]
    conn.close()
    return apps
