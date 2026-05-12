import time
import logging

import pyautogui
import pyperclip
from langchain_core.tools import tool

from config import settings
from guardrails.confirmation_gate import ConfirmationDeniedError, request_confirmation
from guardrails.tool_guards import GuardrailError, check_gui_hotkey, is_destructive_gui_action
from tools.screen_context import _run_osascript

logger = logging.getLogger(__name__)

pyautogui.FAILSAFE = True  # move mouse to (0,0) to abort any running sequence
pyautogui.PAUSE = 0        # timing controlled per-action via settings.gui_action_pause

_VALID_TYPES = {
    "move", "click", "double_click", "drag", "scroll",
    "type", "key", "hotkey", "set_clipboard", "focus_window",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _describe_action(action: dict) -> str:
    t = action["type"]
    if t == "move":
        return f"Move mouse to ({action['x']}, {action['y']})"
    if t == "click":
        btn = action.get("button", "left")
        return f"{btn.capitalize()} click at ({action['x']}, {action['y']})"
    if t == "double_click":
        return f"Double-click at ({action['x']}, {action['y']})"
    if t == "drag":
        return f"Drag from ({action['from_x']}, {action['from_y']}) to ({action['to_x']}, {action['to_y']})"
    if t == "scroll":
        direction = "up" if action["amount"] > 0 else "down"
        return f"Scroll {direction} {abs(action['amount'])} at ({action['x']}, {action['y']})"
    if t == "type":
        preview = action["text"][:40] + ("…" if len(action["text"]) > 40 else "")
        return f"Type: {preview!r}"
    if t == "key":
        return f"Press key: {action['key']}"
    if t == "hotkey":
        return f"Hotkey: {'+'.join(action['keys'])}"
    if t == "set_clipboard":
        preview = action["text"][:40] + ("…" if len(action["text"]) > 40 else "")
        return f"Set clipboard: {preview!r}"
    if t == "focus_window":
        return f"Focus window: {action['name']!r}"
    return str(action)


def _validate_action(action: dict) -> None:
    t = action.get("type")
    if t not in _VALID_TYPES:
        raise ValueError(f"Unknown action type: {t!r}. Valid types: {sorted(_VALID_TYPES)}")
    required: dict[str, list[str]] = {
        "move": ["x", "y"], "click": ["x", "y"], "double_click": ["x", "y"],
        "drag": ["from_x", "from_y", "to_x", "to_y"],
        "scroll": ["x", "y", "amount"],
        "type": ["text"], "key": ["key"], "hotkey": ["keys"],
        "set_clipboard": ["text"], "focus_window": ["name"],
    }
    for field in required.get(t, []):
        if field not in action:
            raise ValueError(f"Action {t!r} missing required field {field!r}")
    if t == "hotkey":
        check_gui_hotkey(action["keys"])


def _run_action(action: dict) -> None:
    t = action["type"]
    if t == "move":
        pyautogui.moveTo(action["x"], action["y"], duration=action.get("duration", 0.2))
    elif t == "click":
        pyautogui.click(action["x"], action["y"], button=action.get("button", "left"))
    elif t == "double_click":
        pyautogui.doubleClick(action["x"], action["y"])
    elif t == "drag":
        pyautogui.dragTo(
            action["to_x"], action["to_y"],
            duration=action.get("duration", 0.5),
            startX=action["from_x"], startY=action["from_y"],
        )
    elif t == "scroll":
        pyautogui.scroll(action["amount"], x=action["x"], y=action["y"])
    elif t == "type":
        pyautogui.write(action["text"], interval=0.03)
    elif t == "key":
        pyautogui.press(action["key"])
    elif t == "hotkey":
        check_gui_hotkey(action["keys"])  # double-check at execution time
        pyautogui.hotkey(*action["keys"])
    elif t == "set_clipboard":
        pyperclip.copy(action["text"])
    elif t == "focus_window":
        _run_osascript(f'tell application "{action["name"]}" to activate')


# ── Read-only tools ───────────────────────────────────────────────────────────

@tool
def get_screen_info() -> str:
    """Return the screen resolution and current cursor position."""
    size = pyautogui.size()
    pos = pyautogui.position()
    return f"Screen: {size.width}x{size.height}  Cursor: ({pos.x}, {pos.y})"


@tool
def get_clipboard_text() -> str:
    """Return the current text content of the system clipboard."""
    text = pyperclip.paste()
    return text if text else "(clipboard is empty)"


@tool
def list_windows() -> str:
    """List the names of all visible application windows (macOS only)."""
    result = _run_osascript(
        'tell application "System Events" to get name of every process where background only is false'
    )
    return result if result else "(no windows found)"


# ── Action tool ───────────────────────────────────────────────────────────────

@tool
def execute_gui_sequence(actions: list) -> str:
    """Execute a sequence of GUI actions (mouse, keyboard, clipboard, window focus)
    after presenting the full plan to the user for approval.

    Each action is a dict with a 'type' field. Supported types:
      move          — {x, y, duration?}
      click         — {x, y, button?}  button: left/right/middle (default left)
      double_click  — {x, y}
      drag          — {from_x, from_y, to_x, to_y, duration?}
      scroll        — {x, y, amount}  positive=up, negative=down
      type          — {text}
      key           — {key}  e.g. "enter", "escape", "tab", "delete"
      hotkey        — {keys: ["cmd", "v"]}
      set_clipboard — {text}
      focus_window  — {name}  (macOS: brings the named app to front)

    Emergency abort: move the mouse to the top-left corner (0, 0) at any time.
    """
    if not actions:
        return "No actions provided."

    # Validate all actions and check blocked hotkeys before asking for approval
    for i, action in enumerate(actions):
        try:
            _validate_action(action)
        except (ValueError, GuardrailError) as e:
            return f"[Blocked] Action {i + 1} invalid: {e}"

    # Build confirmation description with destructive warnings
    has_destructive = any(is_destructive_gui_action(a) for a in actions)
    lines = []
    for i, action in enumerate(actions):
        desc = _describe_action(action)
        prefix = "⚠ DESTRUCTIVE: " if is_destructive_gui_action(action) else ""
        lines.append(f"  {i + 1}. {prefix}{desc}")

    details = "\n".join(lines)
    if has_destructive:
        details = "⚠ WARNING: This sequence contains destructive actions (delete/backspace).\n\n" + details

    try:
        request_confirmation(f"Execute GUI sequence ({len(actions)} action(s))", details)
    except ConfirmationDeniedError as e:
        return f"[Cancelled] {e}"

    # Execute
    executed = 0
    try:
        for action in actions:
            _run_action(action)
            executed += 1
            time.sleep(settings.gui_action_pause)
    except Exception as e:
        logger.error("GUI sequence error at action %d: %s", executed + 1, e)
        return f"[Error] Failed at action {executed + 1} ({_describe_action(actions[executed])}): {e}"

    logger.info("gui_sequence: executed %d actions", executed)
    return f"Executed {executed} action(s) successfully."
