import pathlib

from langchain_core.tools import tool

from guardrails.tool_guards import check_file_path, GuardrailError
from guardrails.confirmation_gate import request_confirmation, ConfirmationDeniedError


@tool
def read_file_tool(path: str) -> str:
    """Read and return the text contents of a file at the given path."""
    try:
        check_file_path(path, mode="read")
        return pathlib.Path(path).read_text(encoding="utf-8")
    except GuardrailError as e:
        return f"[Blocked] {e}"
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def write_file_tool(path: str, content: str) -> str:
    """Write content to a file at the given path. Creates parent directories if needed."""
    try:
        check_file_path(path, mode="write")
        request_confirmation("Write file", f"{path} ({len(content)} chars)")
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {path}"
    except GuardrailError as e:
        return f"[Blocked] {e}"
    except ConfirmationDeniedError as e:
        return f"[Cancelled] {e}"
    except Exception as e:
        return f"Error writing file: {e}"
