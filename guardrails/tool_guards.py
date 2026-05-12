import os
import re
import pathlib
import threading
import time
from collections import defaultdict
from typing import Literal


class GuardrailError(RuntimeError):
    pass


# ── Shell command blocklist ───────────────────────────────────────────────────

SHELL_BLOCKLIST: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\brm\s+(-\S*r\S*f\b|-\S*f\S*r\b)"), "recursive-force-delete"),
    (re.compile(r"\bmkfs\b"), "filesystem-format"),
    (re.compile(r"\bdd\b.+\bof=/dev/"), "raw-device-write"),
    (re.compile(r":\(\)\s*\{.*:\|:"), "fork-bomb"),
    (re.compile(r">\s*/dev/sd[a-z]"), "raw-device-overwrite"),
    (re.compile(r"\bcurl\b.+\|\s*(ba)?sh\b|\bwget\b.+\|\s*(ba)?sh\b"), "pipe-to-shell"),
    (re.compile(r"\beval\b.+\$\("), "eval-subshell"),
    (re.compile(r"\bsudo\b"), "sudo"),
    (re.compile(r"\bsu\b\s+-"), "su-root"),
    (re.compile(r">\s*/etc/(passwd|shadow|sudoers)"), "sensitive-file-overwrite"),
    (re.compile(r"\b(shutdown|reboot|halt|poweroff)\b"), "system-shutdown"),
]


def check_shell_command(command: str) -> None:
    for pattern, label in SHELL_BLOCKLIST:
        if pattern.search(command):
            raise GuardrailError(f"Shell command blocked [{label}]: {command[:120]}")


# ── Python code patterns ──────────────────────────────────────────────────────

BLOCKED_CODE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bos\.system\s*\("), "os.system"),
    (re.compile(r"\bsubprocess\.(run|call|Popen|check_output|getoutput)\s*\("), "subprocess"),
    (re.compile(r"^import\s+subprocess\b|^from\s+subprocess\b", re.M), "import-subprocess"),
    (re.compile(r"\bexec\s*\("), "exec"),
    (re.compile(r"__import__\s*\(\s*['\"]os['\"]"), "dunder-import-os"),
    (re.compile(r"\bctypes\b"), "ctypes"),
    (re.compile(r"\bsocket\.(socket|create_connection)\s*\("), "raw-socket"),
]


def check_python_code(code: str) -> None:
    for pattern, label in BLOCKED_CODE_PATTERNS:
        if pattern.search(code):
            raise GuardrailError(f"Python code blocked [{label}]. Use shell_command_tool for system operations.")


# ── File path protection ──────────────────────────────────────────────────────

_PROTECTED_PATHS: list[pathlib.Path] = [
    pathlib.Path("/etc"),
    pathlib.Path("/usr"),
    pathlib.Path("/bin"),
    pathlib.Path("/sbin"),
    pathlib.Path("/boot"),
    pathlib.Path("/dev"),
    pathlib.Path("/proc"),
    pathlib.Path("/sys"),
    pathlib.Path(os.path.expanduser("~/.ssh")),
    pathlib.Path(os.path.expanduser("~/.aws")),
    pathlib.Path(os.path.expanduser("~/.gnupg")),
    pathlib.Path(".env").resolve(),
]


def check_file_path(path: str, mode: Literal["read", "write"]) -> None:
    if "\x00" in path:
        raise GuardrailError("Null byte in file path")
    try:
        resolved = pathlib.Path(path).resolve()
    except Exception:
        raise GuardrailError(f"Invalid file path: {path!r}")
    for protected in _PROTECTED_PATHS:
        try:
            resolved.relative_to(protected)
            raise GuardrailError(f"Access to protected path denied: {path!r}")
        except ValueError:
            pass  # not under this protected path — continue checking


# ── GUI / desktop control guards ─────────────────────────────────────────────

_BLOCKED_HOTKEYS: list[tuple[frozenset, str]] = [
    (frozenset({"cmd", "q"}),             "force-quit-app"),
    (frozenset({"ctrl", "alt", "delete"}), "system-interrupt"),
    (frozenset({"cmd", "option", "esc"}), "force-quit-dialog"),
]

_DESTRUCTIVE_KEYS: frozenset[str] = frozenset({"delete", "backspace", "clear"})
_DESTRUCTIVE_HOTKEY_SUBSETS: list[frozenset] = [
    frozenset({"cmd", "delete"}),    # move to trash
    frozenset({"cmd", "backspace"}), # delete line / move to trash
    frozenset({"shift", "delete"}),  # permanent delete in some apps
]


def check_gui_hotkey(keys: list[str]) -> None:
    key_set = frozenset(k.lower() for k in keys)
    for blocked, label in _BLOCKED_HOTKEYS:
        if key_set == blocked:
            raise GuardrailError(f"Hotkey blocked ({label}): {keys}")


def is_destructive_gui_action(action: dict) -> bool:
    """Return True if the action involves a delete/backspace key or destructive hotkey."""
    t = action.get("type", "")
    if t == "key" and action.get("key", "").lower() in _DESTRUCTIVE_KEYS:
        return True
    if t == "hotkey":
        key_set = frozenset(k.lower() for k in action.get("keys", []))
        if key_set & _DESTRUCTIVE_KEYS:
            return True
        for d in _DESTRUCTIVE_HOTKEY_SUBSETS:
            if d <= key_set:
                return True
    return False


# ── Outbound message rate limiting ────────────────────────────────────────────

_rate_lock = threading.Lock()
_send_timestamps: dict[str, list[float]] = defaultdict(list)

RATE_LIMITS: dict[str, tuple[int, int]] = {
    "send_email_tool":    (3, 300),  # 3 per 5 min
    "send_telegram_tool": (5, 60),   # 5 per 1 min
}


def check_rate_limit(tool_name: str) -> None:
    if tool_name not in RATE_LIMITS:
        return
    max_calls, window_secs = RATE_LIMITS[tool_name]
    now = time.monotonic()
    with _rate_lock:
        _send_timestamps[tool_name] = [
            t for t in _send_timestamps[tool_name] if now - t < window_secs
        ]
        if len(_send_timestamps[tool_name]) >= max_calls:
            oldest = _send_timestamps[tool_name][0]
            wait = int(window_secs - (now - oldest)) + 1
            raise GuardrailError(
                f"Rate limit exceeded for {tool_name}: "
                f"max {max_calls} per {window_secs}s. Retry in ~{wait}s."
            )
        _send_timestamps[tool_name].append(now)
