import ast
import importlib
import pathlib
import re
import sys
import textwrap

from langchain_core.tools import tool

from guardrails.confirmation_gate import ConfirmationDeniedError, request_confirmation
from guardrails.tool_guards import GuardrailError, check_python_code

_TOOLS_DIR = pathlib.Path(__file__).parent
_INIT_PATH = _TOOLS_DIR / "__init__.py"

_TOOL_TEMPLATE = '''\
from langchain_core.tools import tool
from guardrails.confirmation_gate import ConfirmationDeniedError, request_confirmation
from guardrails.tool_guards import GuardrailError

@tool
def {func_name}({params}) -> str:
    """{description}"""
    try:
{indented_body}
    except GuardrailError as e:
        return f"[Blocked] {{e}}"
    except ConfirmationDeniedError as e:
        return f"[Cancelled] {{e}}"
    except Exception as e:
        return f"Error: {{e}}"
'''

_MARKER = "# === BEGIN AGENT-CREATED TOOLS ==="


def _assemble_tool_file(func_name: str, description: str, body: str) -> str:
    indented = textwrap.indent(textwrap.dedent(body).strip(), "        ")
    return _TOOL_TEMPLATE.format(
        func_name=func_name,
        params="",
        description=description,
        indented_body=indented,
    )


def _update_init(tool_file_stem: str, func_name: str) -> None:
    """Rewrite tools/__init__.py to include the new dynamic tool."""
    current = _INIT_PATH.read_text(encoding="utf-8")
    backup = _INIT_PATH.with_suffix(".py.bak")
    backup.write_text(current, encoding="utf-8")

    new_import = f"from tools.{tool_file_stem} import {func_name}"

    if _MARKER in current:
        static_section, _, dynamic_raw = current.partition(_MARKER)
    else:
        # First dynamic tool: split off get_all_tools and insert marker before it
        split_point = current.rfind("\ndef get_all_tools")
        static_section = current[:split_point] + "\n"
        dynamic_raw = ""

    # Collect existing dynamic imports
    dynamic_imports = [
        line.strip()
        for line in dynamic_raw.splitlines()
        if line.strip().startswith("from tools.") and "import" in line
    ]
    if new_import not in dynamic_imports:
        dynamic_imports.append(new_import)

    # Collect all tool symbol names from dynamic imports
    dynamic_symbols = []
    for imp in dynamic_imports:
        m = re.search(r"import\s+(.+)$", imp)
        if m:
            dynamic_symbols.extend(s.strip() for s in m.group(1).split(","))

    # Rebuild get_all_tools with original static tools + dynamic ones
    original_tools = re.findall(r"^\s+([\w]+),?$", dynamic_raw or current, re.MULTILINE)
    # Parse original static return list from static_section
    static_match = re.search(
        r"def get_all_tools\(\):\s+return \[(.*?)\]",
        static_section,
        re.DOTALL,
    )
    static_tools = []
    if static_match:
        static_tools = [
            t.strip().rstrip(",")
            for t in static_match.group(1).split("\n")
            if t.strip().rstrip(",")
        ]
        # Remove the old get_all_tools from static_section
        static_section = static_section[: static_match.start()].rstrip()

    all_tools = static_tools + [s for s in dynamic_symbols if s not in static_tools]
    tool_list_body = "\n".join(f"        {t}," for t in all_tools)
    get_all_tools_fn = f"\n\ndef get_all_tools():\n    return [\n{tool_list_body}\n    ]\n"

    new_content = (
        static_section
        + "\n"
        + _MARKER + "\n"
        + "\n".join(dynamic_imports)
        + "\n"
        + get_all_tools_fn
    )

    # Validate syntax before writing
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        backup.unlink(missing_ok=True)
        raise RuntimeError(f"Generated __init__.py has syntax error: {e}") from e

    _INIT_PATH.write_text(new_content, encoding="utf-8")


@tool
def create_new_tool(tool_name: str, description: str, implementation_code: str) -> str:
    """Create a new Python tool and hot-reload the agent to activate it immediately.
    tool_name: snake_case identifier (e.g. 'fetch_weather'). Becomes the function + filename.
    description: one-line description the LLM sees as the tool's purpose.
    implementation_code: the function body only (plain Python, no def/decorator). The tool
    wrapper, @tool decorator, imports, and error handling are added automatically.
    The full generated file is shown for approval before anything is written."""
    try:
        # Validate name format
        if not re.match(r"^[a-z][a-z0-9_]+$", tool_name):
            return "Error: tool_name must be lowercase snake_case starting with a letter."

        func_name = tool_name
        file_stem = f"{tool_name}_tool"
        target_path = _TOOLS_DIR / f"{file_stem}.py"

        if target_path.exists():
            return f"Error: {target_path.name} already exists. Choose a different name."

        # Safety check on the implementation body
        check_python_code(implementation_code)

        # Assemble full file
        full_code = _assemble_tool_file(func_name, description, implementation_code)

        # Syntax check
        try:
            ast.parse(full_code)
        except SyntaxError as e:
            return f"Syntax error in generated tool file: {e}"

        # Human approval — show the full file
        request_confirmation("Create tool", full_code)

        # Write the file
        target_path.write_text(full_code, encoding="utf-8")

        # Verify it imports cleanly
        spec = importlib.util.spec_from_file_location(f"tools.{file_stem}", target_path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            target_path.unlink(missing_ok=True)
            return f"Error: tool file failed to import after writing: {e}"

        # Update tools/__init__.py
        try:
            _update_init(file_stem, func_name)
        except Exception as e:
            target_path.unlink(missing_ok=True)
            return f"Error updating tools/__init__.py: {e}"

        # Hot-reload
        from agent import rebuild_agent
        rebuild_agent()

        return (
            f"Tool '{tool_name}' created at tools/{file_stem}.py and loaded. "
            f"You can use it in the next message."
        )

    except GuardrailError as e:
        return f"[Blocked] {e}"
    except ConfirmationDeniedError as e:
        return f"[Cancelled] {e}"
    except Exception as e:
        return f"Error: {e}"
