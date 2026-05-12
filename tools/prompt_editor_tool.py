import difflib
import pathlib

from langchain_core.tools import tool

from guardrails.confirmation_gate import ConfirmationDeniedError, request_confirmation

_PROMPT_PATH = pathlib.Path(__file__).parent.parent / "prompts" / "system_prompt.md"


@tool
def read_system_prompt() -> str:
    """Return the current system prompt. Use this before proposing any changes to it."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading system prompt: {e}"


@tool
def update_system_prompt(new_prompt: str) -> str:
    """Replace the system prompt with new_prompt. A unified diff is shown for approval
    before anything is written. The agent rebuilds automatically after approval.
    The {current_datetime} placeholder must be preserved in new_prompt."""
    try:
        if "{current_datetime}" not in new_prompt:
            return "Error: new_prompt must contain the {current_datetime} placeholder."

        current = _PROMPT_PATH.read_text(encoding="utf-8")

        if current == new_prompt:
            return "No changes — new prompt is identical to the current one."

        diff_lines = list(difflib.unified_diff(
            current.splitlines(keepends=True),
            new_prompt.splitlines(keepends=True),
            fromfile="system_prompt.md (current)",
            tofile="system_prompt.md (proposed)",
            n=3,
        ))
        diff_text = "".join(diff_lines) if diff_lines else "(no textual difference)"

        preview = new_prompt[:600] + ("..." if len(new_prompt) > 600 else "")
        request_confirmation(
            "Update system prompt",
            f"--- DIFF ---\n{diff_text}\n\n--- FULL NEW PROMPT ({len(new_prompt)} chars) ---\n{preview}",
        )

        _PROMPT_PATH.write_text(new_prompt, encoding="utf-8")

        from agent import rebuild_agent
        rebuild_agent()

        return "System prompt updated and agent rebuilt. Changes take effect on the next message."

    except ConfirmationDeniedError as e:
        return f"[Cancelled] {e}"
    except Exception as e:
        return f"Error: {e}"
