"""Builds "Activity Tracker.app" with py2app. Use `activity app install` rather than calling this directly.

The bundle is built in alias mode: it runs the code in this project folder, so edits
take effect the next time you open the app, and the folder has to stay where it is.
"""
import os
import sys

from setuptools import setup

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
VERSION = "0.1.0"

setup(
    name="Activity Tracker",
    app=["src/app.py"],
    options={
        "py2app": {
            "iconfile": "assets/AppIcon.icns",
            "plist": {
                "CFBundleName": "Activity Tracker",
                "CFBundleDisplayName": "Activity Tracker",
                "CFBundleIdentifier": "team.uncover.activity-tracker.app",
                "CFBundleVersion": VERSION,
                "CFBundleShortVersionString": VERSION,
                "LSApplicationCategoryType": "public.app-category.productivity",
                "LSMinimumSystemVersion": "11.0",
                "NSHighResolutionCapable": True,
                # The UI is served by the local Flask server over plain http.
                "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
                "LSEnvironment": {
                    # Inside the app, sys.executable is the app itself, so the
                    # interpreter for the web server is recorded at build time.
                    "ACTIVITY_PYTHON": sys.executable,
                    "ACTIVITY_PROJECT_ROOT": PROJECT_ROOT,
                },
            },
        }
    },
    setup_requires=["py2app"],
)
