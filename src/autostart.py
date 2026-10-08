"""Installs launchd agents so tracking and the web UI start automatically at login."""
import os
import plistlib
import subprocess
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LAUNCH_AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")
LOG_DIR = os.path.expanduser("~/Library/Logs/activity-tracker")
WEB_PORT = 5001

TRACKER_LABEL = "team.uncover.activity-tracker.track"
WEB_LABEL = "team.uncover.activity-tracker.web"


def _agents():
    python = sys.executable
    environment = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONUNBUFFERED": "1",
        "ACTIVITY_PORT": str(WEB_PORT),
    }
    return {
        TRACKER_LABEL: {
            "Label": TRACKER_LABEL,
            "ProgramArguments": [python, "-m", "src.main", "track"],
            "WorkingDirectory": PROJECT_ROOT,
            "EnvironmentVariables": environment,
            "RunAtLoad": True,
            # Restart after a crash, but stay stopped when "Stop recording" exits it cleanly.
            "KeepAlive": {"SuccessfulExit": False},
            "ThrottleInterval": 10,
            "ProcessType": "Background",
            "StandardOutPath": "/dev/null",
            "StandardErrorPath": os.path.join(LOG_DIR, "tracker.log"),
        },
        WEB_LABEL: {
            "Label": WEB_LABEL,
            "ProgramArguments": [python, os.path.join(PROJECT_ROOT, "src", "web", "server.py")],
            "WorkingDirectory": PROJECT_ROOT,
            "EnvironmentVariables": environment,
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 10,
            "ProcessType": "Background",
            "StandardOutPath": os.path.join(LOG_DIR, "web.log"),
            "StandardErrorPath": os.path.join(LOG_DIR, "web.log"),
        },
    }


def _plist_path(label):
    return os.path.join(LAUNCH_AGENTS_DIR, label + ".plist")


def _domain():
    return f"gui/{os.getuid()}"


def _launchctl(*args):
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def _is_loaded(label):
    return _launchctl("print", f"{_domain()}/{label}").returncode == 0


def install():
    os.makedirs(LAUNCH_AGENTS_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    for label, agent in _agents().items():
        path = _plist_path(label)
        if _is_loaded(label):
            _launchctl("bootout", f"{_domain()}/{label}")
        with open(path, "wb") as f:
            plistlib.dump(agent, f)
        result = _launchctl("bootstrap", _domain(), path)
        if result.returncode != 0:
            print(f"Failed to load {label}: {result.stderr.strip()}")
            return
    print("Auto-start installed. Tracking and the web UI now start when you log in.")
    print(f"Timeline: http://activity.localhost:{WEB_PORT}  (or http://127.0.0.1:{WEB_PORT})")
    print(f"Logs: {LOG_DIR}")


def uninstall():
    for label in _agents():
        if _is_loaded(label):
            _launchctl("bootout", f"{_domain()}/{label}")
        try:
            os.remove(_plist_path(label))
        except FileNotFoundError:
            pass
    print("Auto-start removed. Tracking and the web UI are stopped.")


def status():
    for label in _agents():
        installed = os.path.exists(_plist_path(label))
        loaded = _is_loaded(label)
        print(f"{label}: {'installed' if installed else 'not installed'}, {'loaded' if loaded else 'not loaded'}")
