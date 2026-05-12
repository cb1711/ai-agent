"""Detect the active application and browser URL on macOS via AppleScript.

Falls back gracefully on non-macOS platforms (returns empty strings so the
restriction check is a no-op).
"""

import subprocess
import sys
from urllib.parse import urlparse

# AppleScript templates keyed by the substring that appears in the app name
_BROWSER_URL_SCRIPTS: list[tuple[str, str]] = [
    ("safari",  'tell application "Safari" to get URL of current tab of window 1'),
    ("chrome",  'tell application "Google Chrome" to get URL of active tab of window 1'),
    ("arc",     'tell application "Arc" to get URL of active tab of window 1'),
    ("brave",   'tell application "Brave Browser" to get URL of active tab of window 1'),
    ("edge",    'tell application "Microsoft Edge" to get URL of active tab of window 1'),
    ("firefox", 'tell application "Firefox" to get URL of active tab of window 1'),
]

_IS_MACOS = sys.platform == "darwin"


def _run_osascript(script: str, timeout: float = 2.0) -> str:
    """Run an AppleScript and return stdout, or '' on any error."""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def get_active_app() -> str:
    """Return the name of the frontmost application (macOS only)."""
    if not _IS_MACOS:
        return ""
    return _run_osascript(
        'tell application "System Events" to get name of first process where frontmost is true'
    )


def get_browser_url(app_name: str) -> str:
    """Return the active tab URL if app_name is a known browser, else ''."""
    if not _IS_MACOS or not app_name:
        return ""
    lower = app_name.lower()
    for keyword, script in _BROWSER_URL_SCRIPTS:
        if keyword in lower:
            return _run_osascript(script)
    return ""


def extract_domain(url: str) -> str:
    """Return the bare domain (without www.) from a URL string."""
    if not url:
        return ""
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.removeprefix("www.")
    except Exception:
        return ""


def is_restricted(app_name: str, url: str) -> bool:
    """Return True if app_name or the domain of url is in the configured restricted lists."""
    from config import settings

    if app_name:
        lower_app = app_name.lower()
        for entry in settings.screen_record_restricted_apps:
            if entry and entry.lower() in lower_app:
                return True

    if url:
        domain = extract_domain(url)
        for entry in settings.screen_record_restricted_domains:
            if not entry:
                continue
            entry = entry.lower()
            if domain == entry or domain.endswith("." + entry):
                return True

    return False
