from langchain_core.tools import tool
from langchain_experimental.tools import PythonREPLTool

from guardrails.tool_guards import check_python_code, GuardrailError

_repl = PythonREPLTool()


@tool
def python_repl_tool(code: str) -> str:
    """Execute Python code in a persistent REPL and return stdout/stderr.
    Use for calculations, data processing, or any Python snippet.
    The REPL state (variables) persists across calls within a session."""
    try:
        check_python_code(code)
        return _repl.run(code)
    except GuardrailError as e:
        return f"[Blocked] {e}"
    except Exception as e:
        return f"Error: {e}"
