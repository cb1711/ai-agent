import pathlib

from langchain_core.tools import tool


@tool
def read_file_tool(path: str) -> str:
    """Read and return the text contents of a file at the given path."""
    try:
        return pathlib.Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def write_file_tool(path: str, content: str) -> str:
    """Write content to a file at the given path. Creates parent directories if needed."""
    try:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error writing file: {e}"
