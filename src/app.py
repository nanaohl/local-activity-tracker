"""Native Mac window around the web UI, so the tracker has a Dock icon.

Run with `activity app` (or from the built "Activity Tracker.app" bundle).
"""
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

import objc
from AppKit import (
    NSApp,
    NSApplication,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSImage,
    NSMenu,
    NSMenuItem,
    NSScreen,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
    NSWorkspace,
)
from Foundation import NSURL, NSURLRequest, NSObject, NSMakeRect
from WebKit import WKWebView, WKWebViewConfiguration

PROJECT_ROOT = os.environ.get("ACTIVITY_PROJECT_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
# Inside the app bundle sys.executable is the app itself; the build records a real interpreter.
PYTHON = os.environ.get("ACTIVITY_PYTHON") or sys.executable
PORT = int(os.environ.get("ACTIVITY_PORT", 5001))
BASE_URL = f"http://127.0.0.1:{PORT}"
SERVER_TIMEOUT = 20
WINDOW_SIZE = (1320, 860)
MIN_WINDOW_SIZE = (720, 520)


# --- Web server ------------------------------------------------------------

def server_running():
    try:
        urllib.request.urlopen(BASE_URL + "/api/recording", timeout=1).read()
        return True
    except (urllib.error.URLError, OSError):
        return False


def start_server():
    """Starts the Flask server unless one is already listening. Returns the process we started, if any."""
    if server_running():
        return None
    process = subprocess.Popen(
        [PYTHON, os.path.join(PROJECT_ROOT, "src", "web", "server.py")],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.time() + SERVER_TIMEOUT
    while time.time() < deadline:
        if server_running():
            return process
        if process.poll() is not None:
            raise RuntimeError("The activity web server stopped while starting up.")
        time.sleep(0.2)
    raise RuntimeError(f"The activity web server did not answer on {BASE_URL}.")


# --- App -------------------------------------------------------------------

class AppDelegate(NSObject):
    def initWithServer_(self, server_process):
        self = objc.super(AppDelegate, self).init()
        self.server_process = server_process
        self.window = None
        self.webview = None
        return self

    # Window ---------------------------------------------------------------

    def buildWindow(self):
        width, height = WINDOW_SIZE
        screen = NSScreen.mainScreen().visibleFrame() if NSScreen.mainScreen() else None
        if screen is not None:
            width = min(width, int(screen.size.width) - 40)
            height = min(height, int(screen.size.height) - 40)
        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable
            | NSWindowStyleMaskResizable
        )
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, width, height), style, NSBackingStoreBuffered, False
        )
        window.setTitle_("Activity Tracker")
        window.setMinSize_((MIN_WINDOW_SIZE[0], MIN_WINDOW_SIZE[1]))
        # Remembers size and position between launches.
        if not window.setFrameUsingName_("ActivityTrackerWindow"):
            window.center()
        window.setFrameAutosaveName_("ActivityTrackerWindow")

        webview = WKWebView.alloc().initWithFrame_configuration_(
            window.contentView().bounds(), WKWebViewConfiguration.alloc().init()
        )
        webview.setAutoresizingMask_(1 << 1 | 1 << 4)  # width | height
        webview.setUIDelegate_(self)
        window.contentView().addSubview_(webview)

        self.window, self.webview = window, webview
        self.loadTimeline_(None)
        window.makeKeyAndOrderFront_(None)

    # Links with target="_blank" (e.g. a ClickUp ticket) open in the default browser.
    def webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
        self, webview, configuration, action, features
    ):
        url = action.request().URL()
        if url is not None:
            NSWorkspace.sharedWorkspace().openURL_(url)
        return None

    # Actions --------------------------------------------------------------

    def loadTimeline_(self, sender):
        self.webview.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(BASE_URL)))

    def reload_(self, sender):
        self.webview.reload()

    def openInBrowser_(self, sender):
        url = self.webview.URL() or NSURL.URLWithString_(BASE_URL)
        NSWorkspace.sharedWorkspace().openURL_(url)

    # Lifecycle ------------------------------------------------------------

    def applicationDidFinishLaunching_(self, notification):
        self.buildWindow()
        NSApp.activateIgnoringOtherApps_(True)

    def applicationShouldHandleReopen_hasVisibleWindows_(self, app, visible):
        if not visible and self.window is not None:
            self.window.makeKeyAndOrderFront_(None)
        return True

    def applicationShouldTerminateAfterLastWindowClosed_(self, app):
        return True

    def applicationWillTerminate_(self, notification):
        # Leave a server that was already running (e.g. the launchd agent) alone.
        # Recording keeps going either way: the tracker is its own process.
        if self.server_process is not None and self.server_process.poll() is None:
            self.server_process.terminate()


def build_menu(delegate):
    def item(menu, title, action, key, target=None, modifier=None):
        entry = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key)
        if target is not None:
            entry.setTarget_(target)
        if modifier is not None:
            entry.setKeyEquivalentModifierMask_(modifier)
        menu.addItem_(entry)
        return entry

    def submenu(title):
        parent = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, None, "")
        menu = NSMenu.alloc().initWithTitle_(title)
        parent.setSubmenu_(menu)
        menubar.addItem_(parent)
        return menu

    menubar = NSMenu.alloc().init()
    NSApp.setMainMenu_(menubar)

    app_menu = submenu("Activity Tracker")
    item(app_menu, "About Activity Tracker", "orderFrontStandardAboutPanel:", "")
    app_menu.addItem_(NSMenuItem.separatorItem())
    item(app_menu, "Hide Activity Tracker", "hide:", "h")
    item(app_menu, "Hide Others", "hideOtherApplications:", "h", modifier=(1 << 19) | (1 << 20))
    item(app_menu, "Show All", "unhideAllApplications:", "")
    app_menu.addItem_(NSMenuItem.separatorItem())
    item(app_menu, "Quit Activity Tracker", "terminate:", "q")

    edit_menu = submenu("Edit")
    item(edit_menu, "Undo", "undo:", "z")
    item(edit_menu, "Redo", "redo:", "Z")
    edit_menu.addItem_(NSMenuItem.separatorItem())
    item(edit_menu, "Cut", "cut:", "x")
    item(edit_menu, "Copy", "copy:", "c")
    item(edit_menu, "Paste", "paste:", "v")
    item(edit_menu, "Select All", "selectAll:", "a")

    view_menu = submenu("View")
    item(view_menu, "Timeline", "loadTimeline:", "1", target=delegate)
    item(view_menu, "Reload", "reload:", "r", target=delegate)
    item(view_menu, "Open in Browser", "openInBrowser:", "b", target=delegate)
    view_menu.addItem_(NSMenuItem.separatorItem())
    item(view_menu, "Enter Full Screen", "toggleFullScreen:", "f", modifier=(1 << 19) | (1 << 20))

    window_menu = submenu("Window")
    item(window_menu, "Minimize", "performMiniaturize:", "m")
    item(window_menu, "Zoom", "performZoom:", "")
    NSApp.setWindowsMenu_(window_menu)


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    server_process = start_server()

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

    icon_path = os.path.join(PROJECT_ROOT, "assets", "AppIcon.icns")
    if os.path.exists(icon_path):
        image = NSImage.alloc().initWithContentsOfFile_(icon_path)
        if image is not None:
            app.setApplicationIconImage_(image)

    delegate = AppDelegate.alloc().initWithServer_(server_process)
    app.setDelegate_(delegate)
    build_menu(delegate)
    app.run()


if __name__ == "__main__":
    main()
