import subprocess

from langchain_core.tools import tool

from guardrails.tool_guards import check_shell_command, GuardrailError
from guardrails.confirmation_gate import request_confirmation, ConfirmationDeniedError


@tool
def shell_command_tool(command: str) -> str:
    """Execute a shell command and return its combined stdout and stderr.
    Use for system operations, running scripts, or checking system state.
    Commands time out after 30 seconds."""
    try:
        check_shell_command(command)
        request_confirmation("Run shell command", command)
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        return output.strip() or f"(exit code {result.returncode}, no output)"
    except GuardrailError as e:
        return f"[Blocked] {e}"
    except ConfirmationDeniedError as e:
        return f"[Cancelled] {e}"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30 seconds"
    except Exception as e:
        return f"Error: {e}"
