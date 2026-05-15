"""Read UI element content from any macOS app via the Accessibility API."""

import logging
from AppKit import NSWorkspace
from ApplicationServices import (
    AXUIElementCreateApplication,
    AXUIElementCreateSystemWide,
    AXUIElementCopyAttributeValue,
    AXUIElementCopyAttributeNames,
    kAXErrorSuccess,
    kAXRoleAttribute,
    kAXTitleAttribute,
    kAXValueAttribute,
    kAXChildrenAttribute,
    kAXDescriptionAttribute,
    kAXFocusedApplicationAttribute,
    kAXRoleDescriptionAttribute,
    kAXSelectedTextAttribute,
)
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_SKIP_ROLES = {"AXScrollBar", "AXSplitter", "AXGrowArea", "AXUnknown"}
_MAX_DEPTH = 12
_MAX_NODES = 300


def _ax_attr(element, attr):
    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    return value if err == kAXErrorSuccess else None


def _ax_attr_names(element):
    err, names = AXUIElementCopyAttributeNames(element, None)
    return names if err == kAXErrorSuccess else []


def _collect_text(element, depth: int, lines: list[str], seen: set) -> None:
    if depth > _MAX_DEPTH or len(lines) >= _MAX_NODES:
        return

    element_id = id(element)
    if element_id in seen:
        return
    seen.add(element_id)

    role = _ax_attr(element, kAXRoleAttribute) or ""
    if role in _SKIP_ROLES:
        return

    title = _ax_attr(element, kAXTitleAttribute) or ""
    value = _ax_attr(element, kAXValueAttribute) or ""
    desc = _ax_attr(element, kAXDescriptionAttribute) or ""

    # Prefer value for text fields, title for controls
    text = ""
    if role in {"AXTextField", "AXTextArea", "AXComboBox", "AXStaticText"}:
        text = str(value or title or desc).strip()
    else:
        text = str(title or desc or value).strip()

    if text:
        indent = "  " * depth
        lines.append(f"{indent}[{role}] {text}")

    children = _ax_attr(element, kAXChildrenAttribute)
    if children:
        for child in children:
            _collect_text(child, depth + 1, lines, seen)


def _frontmost_pid() -> int | None:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.processIdentifier() if app else None


def _pid_for_name(name: str) -> int | None:
    apps = NSWorkspace.sharedWorkspace().runningApplications()
    lower = name.lower()
    for app in apps:
        if app.localizedName() and lower in app.localizedName().lower():
            return app.processIdentifier()
    return None


@tool
def read_ax_content(app_name: str = "") -> str:
    """Read the visible UI element content of a macOS app using the Accessibility API.

    Returns the text, labels, and values of all UI elements in the app's window.
    Much more reliable than OCR for reading structured UI content like text fields,
    buttons, menus, and document text.

    Args:
        app_name: Name of the app to read (e.g. "Safari", "Xcode", "Finder").
                  Leave empty to read the currently focused/frontmost app.

    Requires Accessibility permissions: System Settings → Privacy & Security →
    Accessibility → enable for Terminal (or the app running the agent).
    """
    if app_name:
        pid = _pid_for_name(app_name)
        if pid is None:
            return f"[Error] No running app found matching {app_name!r}."
    else:
        pid = _frontmost_pid()
        if pid is None:
            return "[Error] Could not determine the frontmost application."
        app_name = NSWorkspace.sharedWorkspace().frontmostApplication().localizedName() or "Unknown"

    ax_app = AXUIElementCreateApplication(pid)
    lines: list[str] = []
    _collect_text(ax_app, depth=0, lines=lines, seen=set())

    if not lines:
        return (
            f"[No content] Could not read UI elements for {app_name!r}.\n"
            "Check that Accessibility permissions are granted for this terminal in "
            "System Settings → Privacy & Security → Accessibility."
        )

    header = f"=== Accessibility content: {app_name} (PID {pid}) ===\n"
    return header + "\n".join(lines)


@tool
def get_ax_selected_text(app_name: str = "") -> str:
    """Get the currently selected text in a macOS app via the Accessibility API.

    Faster and more reliable than clipboard-based approaches for reading selections.

    Args:
        app_name: App to query. Leave empty to use the frontmost app.
    """
    if app_name:
        pid = _pid_for_name(app_name)
        if pid is None:
            return f"[Error] No running app found matching {app_name!r}."
    else:
        pid = _frontmost_pid()
        if pid is None:
            return "[Error] Could not determine the frontmost application."

    system = AXUIElementCreateSystemWide()
    focused_app = _ax_attr(system, kAXFocusedApplicationAttribute)
    if focused_app is None:
        return "[Error] Could not get focused application element."

    # Walk to find focused element with selected text
    def _find_selected(el, depth=0):
        if depth > 6:
            return None
        attrs = _ax_attr_names(el)
        if kAXSelectedTextAttribute in (attrs or []):
            val = _ax_attr(el, kAXSelectedTextAttribute)
            if val:
                return str(val)
        children = _ax_attr(el, kAXChildrenAttribute)
        if children:
            for child in children:
                result = _find_selected(child, depth + 1)
                if result:
                    return result
        return None

    text = _find_selected(focused_app)
    if not text:
        return "(No text currently selected)"
    return text
