from flask import Flask, abort, jsonify, redirect, render_template, request, send_file
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse
import hashlib
import os
import plistlib
import signal
import subprocess
import sys
import threading
import time

# Add the src directory to the Python path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
sys.path.append(SRC_DIR)

import clickup
from database import (
    assign_task,
    create_table,
    delete_activities,
    get_activities_between,
    get_activities_for_date,
    get_daily_summary,
    get_weekly_summary,
    get_monthly_summary,
    get_recent_tasks,
    get_top_apps,
    get_yearly_summary,
    mark_activities_added,
    merge_activities,
    refresh_known_tasks,
    save_tasks,
)

PID_FILE = os.path.join(PROJECT_ROOT, "tracker.pid")
ICON_CACHE_DIR = os.path.expanduser("~/Library/Caches/activity-tracker/icons")
APP_DIRS = [
    "/Applications",
    "/Applications/Utilities",
    "/System/Applications",
    "/System/Applications/Utilities",
    os.path.expanduser("~/Applications"),
]
# Consecutive rows for the same app/window/URL separated by at most this gap are shown as one entry.
MERGE_GAP = timedelta(seconds=5)
# Rows recorded when the tracker couldn't read the frontmost app (e.g. screen locked).
UNIDENTIFIED_APPS = {'Unknown'}

icon_lock = threading.Lock()

app = Flask(__name__, template_folder='templates', static_folder='static')
create_table()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/charts')
def charts():
    return redirect('/summary')


@app.route('/api/data')
def get_data():
    now = datetime.now()
    daily_summary = get_daily_summary(now.day, now.month, now.year)
    weekly_summary = get_weekly_summary(now.isocalendar()[1], now.year)
    monthly_summary = get_monthly_summary(now.month, now.year)
    yearly_summary = get_yearly_summary(now.year)

    return jsonify({
        'daily': daily_summary,
        'weekly': weekly_summary,
        'monthly': monthly_summary,
        'yearly': yearly_summary
    })


# --- Timeline --------------------------------------------------------------

def tracker_pid():
    """Returns the pid of the running tracker, or None."""
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError):
        return None
    except PermissionError:
        return None


def row_task(row):
    """The ClickUp task joined onto an activity row, or None."""
    if not row['task_id']:
        return None
    return {
        'id': row['task_id'],
        'custom_id': row['task_custom_id'],
        'name': row['task_name'] or row['task_id'],
        'status': row['task_status'],
        'status_color': row['task_status_color'],
        'url': row['task_url'] or f"https://app.clickup.com/t/{row['task_id']}",
        'list_name': row['task_list_name'],
    }


def build_entries(rows, latest_id, recording, day):
    """Collapses raw per-switch rows into timeline entries, clipped to the given day."""
    now = datetime.now()
    day_end = day + timedelta(days=1)
    entries = []
    for row in rows:
        start = datetime.fromisoformat(row['start_time'])
        if row['end_time']:
            end = datetime.fromisoformat(row['end_time'])
        elif recording and row['id'] == latest_id:
            end = now  # the activity currently being tracked
        else:
            continue  # abandoned row from a tracker that didn't shut down cleanly
        end = min(end, day_end)
        idle = row['idle_seconds']
        task = row_task(row)

        prev = entries[-1] if entries else None
        if (
            prev
            and (prev['app'], prev['title'], prev['url']) == (row['app_name'], row['window_title'], row['url'])
            and (prev['task'] or {}).get('id') == row['task_id']
            and start - prev['_end'] <= MERGE_GAP
        ):
            prev['ids'].append(row['id'])
            prev['_end'] = max(prev['_end'], end)
            if idle is not None:
                prev['idle'] = (prev['idle'] or 0) + idle
            prev['added'] = prev['added'] and bool(row['added'])
            continue

        entries.append({
            'ids': [row['id']],
            'app': row['app_name'],
            'title': row['window_title'] or '',
            'url': row['url'],
            '_start': start,
            '_end': end,
            'idle': idle,
            'added': bool(row['added']),
            'task': task,
        })

    for entry in entries:
        start, end = entry.pop('_start'), entry.pop('_end')
        entry['start'] = start.isoformat(timespec='seconds')
        entry['end'] = end.isoformat(timespec='seconds')
        entry['duration'] = max(0, round((end - start).total_seconds()))
    return entries


# Number of apps with their own colour; matches the palette size in static/common.js.
COLOR_SLOTS = 7


@app.route('/api/app-colors')
def app_colors():
    """All-time app order used to give each app the same colour on every page and period."""
    return jsonify({'apps': get_top_apps(COLOR_SLOTS, exclude=tuple(UNIDENTIFIED_APPS))})


@app.route('/api/day')
def get_day():
    date_str = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')
    try:
        day = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        abort(400, 'date must be YYYY-MM-DD')
    recording = tracker_pid() is not None
    rows, latest_id = get_activities_for_date(date_str)
    return jsonify({
        'date': date_str,
        'recording': recording,
        'entries': build_entries(rows, latest_id, recording, day),
    })


# --- Summary ---------------------------------------------------------------

TOP_ITEMS_PER_APP = 8


def period_bounds(period, day):
    """Returns (start, end, bucket_starts) for a day, ISO week or month containing `day`."""
    if period == 'day':
        start = day
        end = start + timedelta(days=1)
        buckets = [start + timedelta(hours=h) for h in range(24)]
    elif period == 'week':
        start = day - timedelta(days=day.weekday())
        end = start + timedelta(days=7)
        buckets = [start + timedelta(days=d) for d in range(7)]
    else:
        start = day.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        buckets = [start + timedelta(days=d) for d in range((end - start).days)]
    return start, end, buckets


def item_label(row):
    """What an activity was about: the website for browsers, otherwise the window title."""
    if row['url']:
        host = urlparse(row['url']).netloc
        if host:
            return host[4:] if host.startswith('www.') else host
    return row['window_title'] or '(no title)'


def build_summary(rows, latest_id, recording, period, start, end, bucket_starts, include_unidentified):
    now = datetime.now()
    bucket_ends = bucket_starts[1:] + [end]
    buckets = [defaultdict(float) for _ in bucket_starts]
    apps = defaultdict(lambda: {'seconds': 0.0, 'idle': 0.0, 'idle_known': 0.0, 'items': defaultdict(float)})
    sites = defaultdict(float)
    unidentified = 0.0

    for row in rows:
        row_start = datetime.fromisoformat(row['start_time'])
        if row['end_time']:
            row_end = datetime.fromisoformat(row['end_time'])
        elif recording and row['id'] == latest_id:
            row_end = now
        else:
            continue
        full = (row_end - row_start).total_seconds()
        clip_start, clip_end = max(row_start, start), min(row_end, end)
        seconds = (clip_end - clip_start).total_seconds()
        if seconds <= 0:
            continue
        if row['app_name'] in UNIDENTIFIED_APPS:
            unidentified += seconds
            if not include_unidentified:
                continue

        app = apps[row['app_name']]
        app['seconds'] += seconds
        app['items'][item_label(row)] += seconds
        if row['idle_seconds'] is not None and full > 0:
            app['idle'] += row['idle_seconds'] * seconds / full
            app['idle_known'] += seconds
        if row['url']:
            sites[item_label(row)] += seconds

        for i, (b_start, b_end) in enumerate(zip(bucket_starts, bucket_ends)):
            overlap = (min(clip_end, b_end) - max(clip_start, b_start)).total_seconds()
            if overlap > 0:
                buckets[i][row['app_name']] += overlap

    total = sum(a['seconds'] for a in apps.values())
    windows = sorted(
        ((name, label, sec) for name, a in apps.items() for label, sec in a['items'].items()),
        key=lambda item: -item[2],
    )[:10]
    idle_known = sum(a['idle_known'] for a in apps.values())
    idle = sum(a['idle'] for a in apps.values())
    days_active = sum(1 for b in buckets if b) if period != 'day' else (1 if total else 0)

    return {
        'period': period,
        'start': start.strftime('%Y-%m-%d'),
        'end': (end - timedelta(days=1)).strftime('%Y-%m-%d'),
        'recording': recording,
        'total': round(total),
        'idle': round(idle) if idle_known else None,
        'idle_coverage': round(idle_known / total, 3) if total else 0,
        'unidentified': round(unidentified),
        'days_active': days_active,
        'buckets': [
            {'start': b_start.isoformat(timespec='minutes'), 'apps': {k: round(v) for k, v in b.items()}}
            for b_start, b in zip(bucket_starts, buckets)
        ],
        'apps': sorted(
            (
                {
                    'app': name,
                    'seconds': round(a['seconds']),
                    'idle': round(a['idle']) if a['idle_known'] else None,
                    'items': [
                        {'label': label, 'seconds': round(sec)}
                        for label, sec in sorted(a['items'].items(), key=lambda kv: -kv[1])[:TOP_ITEMS_PER_APP]
                    ],
                }
                for name, a in apps.items()
            ),
            key=lambda a: -a['seconds'],
        ),
        'windows': [{'app': name, 'label': label, 'seconds': round(sec)} for name, label, sec in windows],
        'sites': [
            {'label': label, 'seconds': round(sec)}
            for label, sec in sorted(sites.items(), key=lambda kv: -kv[1])[:10]
        ],
    }


@app.route('/summary')
def summary_page():
    return render_template('summary.html')


@app.route('/api/summary')
def get_summary():
    period = request.args.get('period', 'day')
    if period not in ('day', 'week', 'month'):
        abort(400, 'period must be day, week or month')
    date_str = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')
    try:
        day = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        abort(400, 'date must be YYYY-MM-DD')
    include_unidentified = request.args.get('unidentified') == '1'

    start, end, bucket_starts = period_bounds(period, day)
    recording = tracker_pid() is not None
    rows, latest_id = get_activities_between(start, end)
    return jsonify(build_summary(
        rows, latest_id, recording, period, start, end, bucket_starts, include_unidentified
    ))


def _ids_from_request():
    ids = (request.get_json(silent=True) or {}).get('ids')
    if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
        abort(400, 'ids must be a non-empty list of integers')
    return ids


@app.route('/api/entries/delete', methods=['POST'])
def delete_entries():
    delete_activities(_ids_from_request())
    return jsonify({'ok': True})


@app.route('/api/entries/merge', methods=['POST'])
def merge_entries():
    return jsonify({'ok': True, 'id': merge_activities(_ids_from_request())})


@app.route('/api/entries/add', methods=['POST'])
def add_entries():
    mark_activities_added(_ids_from_request())
    return jsonify({'ok': True})


@app.route('/api/entries/ticket', methods=['POST'])
def assign_ticket():
    ids = _ids_from_request()
    task_id = (request.get_json(silent=True) or {}).get('task_id')
    if task_id is None:
        assign_task(ids, None)
        return jsonify({'ok': True, 'task': None})
    if not isinstance(task_id, str) or not task_id:
        abort(400, 'task_id must be a string or null')
    try:
        task = clickup.get_task(task_id)
    except clickup.ClickUpError as e:
        return _clickup_error(e)
    save_tasks([task])
    assign_task(ids, task['id'])
    return jsonify({'ok': True, 'task': task})


# --- ClickUp ---------------------------------------------------------------

RECENT_TASKS = 8


def _clickup_error(error):
    connected = True
    if error.status == 401:
        # ClickUp also answers 401 for tasks in workspaces the token can't access.
        try:
            clickup.get_user()
        except clickup.ClickUpError:
            connected = False
    status = error.status if error.status in (400, 401, 404) else 502
    if status == 401 and connected:
        status = 404
    return jsonify({'error': str(error), 'connected': connected}), status


@app.route('/api/clickup/status')
def clickup_status():
    if not clickup.get_token():
        return jsonify({'connected': False})
    try:
        user = clickup.get_user()
    except clickup.ClickUpError as e:
        return _clickup_error(e)
    return jsonify({'connected': True, 'user': user.get('username') or user.get('email')})


@app.route('/api/clickup/token', methods=['POST'])
def clickup_connect():
    token = ((request.get_json(silent=True) or {}).get('token') or '').strip()
    if not token:
        abort(400, 'token is required')
    try:
        user = clickup.get_user(token=token)
        clickup.save_token(token)
    except clickup.ClickUpError as e:
        return _clickup_error(e)
    return jsonify({'connected': True, 'user': user.get('username') or user.get('email')})


@app.route('/api/clickup/token', methods=['DELETE'])
def clickup_disconnect():
    clickup.delete_token()
    return jsonify({'connected': False})


@app.route('/api/clickup/tasks')
def clickup_tasks():
    recent = get_recent_tasks(RECENT_TASKS)
    try:
        tasks = clickup.assigned_tasks(refresh=request.args.get('refresh') == '1')
    except clickup.ClickUpError as e:
        response, status = _clickup_error(e)
        payload = response.get_json()
        payload['recent'] = recent
        return jsonify(payload), status
    refresh_known_tasks(tasks)
    fresh = {t['id']: t for t in tasks}
    return jsonify({
        'connected': True,
        'recent': [fresh.get(t['id'], t) for t in recent],
        'tasks': tasks,
    })


@app.route('/api/clickup/lookup')
def clickup_lookup():
    try:
        task = clickup.lookup_task(request.args.get('ref', ''))
    except clickup.ClickUpError as e:
        return _clickup_error(e)
    return jsonify({'task': task})


@app.route('/api/recording', methods=['GET'])
def recording_status():
    return jsonify({'recording': tracker_pid() is not None})


@app.route('/api/recording/start', methods=['POST'])
def recording_start():
    if tracker_pid() is None:
        subprocess.Popen(
            [sys.executable, '-m', 'src.main', 'track'],
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # keep recording if the web server stops
        )
        for _ in range(30):
            if tracker_pid() is not None:
                break
            time.sleep(0.1)
    return jsonify({'recording': tracker_pid() is not None})


@app.route('/api/recording/stop', methods=['POST'])
def recording_stop():
    pid = tracker_pid()
    if pid is not None:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            if tracker_pid() is None:
                break
            time.sleep(0.1)
    return jsonify({'recording': tracker_pid() is not None})


# --- App icons -------------------------------------------------------------

def find_app_bundle(app_name):
    for directory in APP_DIRS:
        path = os.path.join(directory, app_name + '.app')
        if os.path.isdir(path):
            return path
    try:
        # Works for running apps whose process name differs from the bundle name.
        out = subprocess.run(
            ['lsappinfo', 'info', '-only', 'bundlepath', app_name],
            capture_output=True, text=True, timeout=2,
        ).stdout
        if '=' in out:
            path = out.split('=', 1)[1].strip().strip('"')
            if path.endswith('.app') and os.path.isdir(path):
                return path
        safe_name = app_name.replace('"', '').replace("'", '')
        out = subprocess.run(
            ['mdfind', f'kMDItemFSName == "{safe_name}.app"'],
            capture_output=True, text=True, timeout=3,
        ).stdout
        for path in out.splitlines():
            if os.path.isdir(path):
                return path
    except (subprocess.SubprocessError, OSError):
        pass
    return None


def find_icns(bundle):
    resources = os.path.join(bundle, 'Contents', 'Resources')
    try:
        with open(os.path.join(bundle, 'Contents', 'Info.plist'), 'rb') as f:
            info = plistlib.load(f)
    except (OSError, plistlib.InvalidFileException):
        info = {}
    for key in ('CFBundleIconFile', 'CFBundleIconName'):
        name = info.get(key)
        if name:
            if not name.endswith('.icns'):
                name += '.icns'
            path = os.path.join(resources, name)
            if os.path.isfile(path):
                return path
    try:
        candidates = sorted(f for f in os.listdir(resources) if f.endswith('.icns'))
    except OSError:
        return None
    return os.path.join(resources, candidates[0]) if candidates else None


@app.route('/api/icon/<path:app_name>')
def app_icon(app_name):
    os.makedirs(ICON_CACHE_DIR, exist_ok=True)
    key = hashlib.sha1(app_name.encode()).hexdigest()
    png = os.path.join(ICON_CACHE_DIR, key + '.png')
    missing = os.path.join(ICON_CACHE_DIR, key + '.missing')
    with icon_lock:
        if not os.path.exists(png) and not os.path.exists(missing):
            _extract_icon(app_name, png, missing)
    if not os.path.exists(png):
        abort(404)
    response = send_file(png, mimetype='image/png')
    response.cache_control.max_age = 86400
    return response


def _extract_icon(app_name, png, missing):
    bundle = find_app_bundle(app_name)
    icns = find_icns(bundle) if bundle else None
    if icns:
        subprocess.run(
            ['sips', '-s', 'format', 'png', '--resampleHeightWidthMax', '64', icns, '--out', png],
            capture_output=True, timeout=10,
        )
    if not os.path.exists(png):
        open(missing, 'w').close()


if __name__ == '__main__':
    app.run(port=int(os.environ.get('ACTIVITY_PORT', 5001)))
