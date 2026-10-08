"""Minimal ClickUp API client. The personal API token is kept in the macOS Keychain."""
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.clickup.com/api/v2"
KEYCHAIN_SERVICE = "activity-tracker.clickup"
KEYCHAIN_ACCOUNT = "api-token"
# Assigned tasks are cached this long so opening the picker stays fast.
TASKS_TTL = 300
MAX_PAGES = 10

# https://app.clickup.com/t/86abc123 or https://app.clickup.com/t/9012345/DEV-42
TASK_URL_RE = re.compile(r"app\.clickup\.com/t/(?:(\d+)/)?([A-Za-z0-9_-]+)")
CUSTOM_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*-\d+$")
TASK_ID_RE = re.compile(r"^#?([a-z0-9]{6,12})$")


class ClickUpError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


# --- Token -----------------------------------------------------------------

def get_token():
    token = os.environ.get("CLICKUP_API_TOKEN")
    if token:
        return token.strip()
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def save_token(token):
    result = subprocess.run(
        ["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w", token],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ClickUpError(f"Could not save the token to the Keychain: {result.stderr.strip()}")
    _clear_cache()


def delete_token():
    subprocess.run(
        ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT],
        capture_output=True, text=True,
    )
    _clear_cache()


# --- API -------------------------------------------------------------------

def _request(path, params=None, token=None):
    token = token or get_token()
    if not token:
        raise ClickUpError("ClickUp is not connected", status=401)
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"Authorization": token, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        try:
            detail = json.load(e).get("err")
        except (ValueError, AttributeError):
            detail = None
        raise ClickUpError(detail or f"ClickUp returned {e.code}", status=e.code)
    except urllib.error.URLError as e:
        raise ClickUpError(f"Could not reach ClickUp: {e.reason}")


def get_user(token=None):
    return _request("/user", token=token)["user"]


def _teams():
    return _request("/team")["teams"]


def task_summary(task):
    """The fields the tracker keeps for a task."""
    status = task.get("status") or {}
    return {
        "id": task["id"],
        "custom_id": task.get("custom_id"),
        "name": task.get("name") or task["id"],
        "status": status.get("status"),
        "status_color": status.get("color"),
        "url": task.get("url") or f"https://app.clickup.com/t/{task['id']}",
        "list_name": (task.get("list") or {}).get("name"),
    }


_cache = {"tasks": None, "fetched": 0.0}
_cache_lock = threading.Lock()


def _clear_cache():
    with _cache_lock:
        _cache.update(tasks=None, fetched=0.0)


def assigned_tasks(refresh=False):
    """Open tasks assigned to the token's user across all workspaces, most recently updated first."""
    with _cache_lock:
        if not refresh and _cache["tasks"] is not None and time.time() - _cache["fetched"] < TASKS_TTL:
            return _cache["tasks"]
    user_id = get_user()["id"]
    tasks = []
    for team in _teams():
        for page in range(MAX_PAGES):
            data = _request(
                f"/team/{team['id']}/task",
                {"assignees[]": [user_id], "subtasks": "true", "order_by": "updated", "page": page},
            )
            tasks.extend(task_summary(t) for t in data.get("tasks", []))
            if data.get("last_page", True) or not data.get("tasks"):
                break
    with _cache_lock:
        _cache.update(tasks=tasks, fetched=time.time())
    return tasks


def get_task(task_id):
    return task_summary(_request(f"/task/{urllib.parse.quote(task_id)}"))


def lookup_task(ref):
    """Resolves a pasted ClickUp link, task ID or custom task ID (e.g. DEV-42). Returns None if not found."""
    ref = (ref or "").strip()
    match = TASK_URL_RE.search(ref)
    team_id, task_ref = (match.group(1), match.group(2)) if match else (None, ref)

    if CUSTOM_ID_RE.match(task_ref):
        team_ids = [team_id] if team_id else [t["id"] for t in _teams()]
        for tid in team_ids:
            try:
                return task_summary(_request(
                    f"/task/{urllib.parse.quote(task_ref)}",
                    {"custom_task_ids": "true", "team_id": tid},
                ))
            except ClickUpError as e:
                if e.status not in (400, 401, 404):
                    raise
        return None

    id_match = TASK_ID_RE.match(task_ref)
    if not id_match:
        return None
    try:
        return get_task(id_match.group(1))
    except ClickUpError as e:
        if e.status in (400, 401, 404):
            return None
        raise
