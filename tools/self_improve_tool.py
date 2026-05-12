import json
import pathlib
from collections import defaultdict

from langchain_core.tools import tool

from audit.store import list_sessions, query_events
from config import settings

_PROMPT_PATH = pathlib.Path(__file__).parent.parent / "prompts" / "system_prompt.md"


@tool
def analyze_agent_performance(lookback_sessions: int = 5) -> str:
    """Analyze recent agent performance from the audit log.
    Returns a structured report: error rates, guardrail blocks, denied confirmations,
    tool usage frequency, and per-tool success rates. Use this before proposing improvements."""
    try:
        sessions = list_sessions(settings.audit_db_path)[:lookback_sessions]
        if not sessions:
            return "No sessions found in audit log."

        session_ids = [s["session_id"] for s in sessions]

        tool_calls: dict[str, int] = defaultdict(int)
        tool_errors: dict[str, int] = defaultdict(int)
        guardrail_blocks: dict[str, int] = defaultdict(int)
        denied_confirmations: list[str] = []
        error_samples: dict[str, list[str]] = defaultdict(list)

        for sid in session_ids:
            events = query_events(settings.audit_db_path, session_id=sid, limit=500)
            for ev in events:
                etype = ev["event_type"]
                source = ev.get("source") or ""
                content = ev.get("content") or ""
                metadata = {}
                if ev.get("metadata"):
                    try:
                        metadata = json.loads(ev["metadata"])
                    except (json.JSONDecodeError, TypeError):
                        pass

                if etype == "tool_call":
                    tool_calls[source] += 1
                elif etype == "tool_error":
                    tool_errors[source] += 1
                    samples = error_samples[source]
                    if len(samples) < 3:
                        samples.append(content[:120])
                elif etype == "guardrail_block":
                    label = metadata.get("label") or source or "unknown"
                    guardrail_blocks[label] += 1
                elif etype == "confirmation":
                    if not metadata.get("approved", True):
                        denied_confirmations.append(
                            f"{metadata.get('action', '?')} — {(metadata.get('details') or '')[:80]}"
                        )

        lines = [
            f"=== Agent Performance Analysis (last {len(session_ids)} session(s)) ===",
            "",
        ]

        lines.append("[TOOL USAGE & SUCCESS RATES]")
        if tool_calls:
            for tool_name in sorted(tool_calls, key=lambda t: -tool_calls[t]):
                calls = tool_calls[tool_name]
                errors = tool_errors.get(tool_name, 0)
                success_pct = round(100 * (calls - errors) / calls) if calls else 0
                lines.append(f"  {tool_name}: {calls} calls, {success_pct}% success")
        else:
            lines.append("  (no tool calls recorded)")

        lines.append("")
        lines.append("[ERROR PATTERNS]")
        if tool_errors:
            for tool_name, count in sorted(tool_errors.items(), key=lambda x: -x[1]):
                lines.append(f"  {tool_name}: {count} error(s)")
                for sample in error_samples.get(tool_name, []):
                    lines.append(f"    sample: {sample}")
        else:
            lines.append("  (no errors recorded)")

        lines.append("")
        lines.append("[GUARDRAIL BLOCKS]")
        if guardrail_blocks:
            for label, count in sorted(guardrail_blocks.items(), key=lambda x: -x[1]):
                lines.append(f"  [{label}]: {count} time(s)")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append("[DENIED CONFIRMATIONS]")
        if denied_confirmations:
            for item in denied_confirmations[:10]:
                lines.append(f"  {item}")
        else:
            lines.append("  (none)")

        return "\n".join(lines)
    except Exception as e:
        return f"Error analyzing performance: {e}"


@tool
def get_current_system_prompt() -> str:
    """Return the current system prompt text. Use this before proposing prompt improvements."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading system prompt: {e}"
