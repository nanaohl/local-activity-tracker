"""Builds and installs "Activity Tracker.app", so the tracker has a Dock icon.

The bundle is built with py2app in alias mode: it runs the code in this project
folder rather than a copy, so keep the folder where it is (rebuild after moving it).
"""
import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_NAME = "Activity Tracker"
INSTALL_DIR = os.path.expanduser("~/Applications")
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
DIST_APP = os.path.join(PROJECT_ROOT, "dist", APP_NAME + ".app")
# What the app needs: the window (WebKit), the web server (flask) and the builder (py2app).
REQUIRED_MODULES = ("WebKit", "flask", "py2app")


def bundle_path(directory=INSTALL_DIR):
    return os.path.join(directory, APP_NAME + ".app")


def _can_build(python):
    if not python or not os.path.exists(python):
        return False
    return subprocess.run(
        [python, "-c", "import " + ", ".join(REQUIRED_MODULES)], capture_output=True
    ).returncode == 0


def find_python():
    """The interpreter used to build and run the app: the project venv, or any that has what's needed."""
    candidates = [VENV_PYTHON, sys.executable, shutil.which("python3")]
    for python in candidates:
        if _can_build(python):
            return python
    raise SystemExit(
        "No Python found with Flask, PyObjC and py2app installed. Create the app's environment with:\n"
        f"  python3 -m venv {os.path.join(PROJECT_ROOT, '.venv')}\n"
        f"  {VENV_PYTHON} -m pip install Flask pyobjc-framework-WebKit py2app"
    )


def build():
    """Builds dist/Activity Tracker.app and returns its path."""
    python = find_python()
    shutil.rmtree(DIST_APP, ignore_errors=True)
    result = subprocess.run(
        [python, "setup_app.py", "py2app", "--alias"], cwd=PROJECT_ROOT,
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not os.path.exists(DIST_APP):
        raise SystemExit(f"Building the app failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    return DIST_APP


def install():
    """Builds the app and puts it in ~/Applications."""
    built = build()
    os.makedirs(INSTALL_DIR, exist_ok=True)
    path = bundle_path()
    shutil.rmtree(path, ignore_errors=True)
    shutil.copytree(built, path, symlinks=True)
    # Ad-hoc signature, so macOS keeps any permissions granted to the app across rebuilds.
    subprocess.run(["codesign", "--force", "--sign", "-", path], capture_output=True)
    subprocess.run(["open", path])
    print(f"Installed {path}")
    print("While it runs, right-click its Dock icon and choose Options → Keep in Dock.")


def uninstall():
    path = bundle_path()
    if os.path.exists(path):
        shutil.rmtree(path)
        print(f"Removed {path}")
    else:
        print(f"{path} is not installed")
    shutil.rmtree(os.path.join(PROJECT_ROOT, "dist"), ignore_errors=True)


def status():
    path = bundle_path()
    print(f"{path}: {'installed' if os.path.exists(path) else 'not installed'}")
    print(f"Built with: {find_python()}")
