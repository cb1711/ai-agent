from langchain_core.tools import tool

from audit.store import query_events, list_sessions
from config import settings

_EVENT_TYPE_ALIASES = {
    "tools": "tool_call",
    "tool_calls": "tool_call",
    "tool_results": "tool_result",
    "messages": "user_message",
    "responses": "agent_response",
    "blocks": "guardrail_block",
    "confirmations": "confirmation",
}


def _fmt_row(row: dict) -> str:
    ts = row["timestamp"][:19].replace("T", " ")
    content = (row["content"] or "")[:120]
    if len(row["content"] or "") > 120:
        content += "…"
    return f"[{ts}] {row['event_type']} ({row['source'] or '-'}): {content}"


@tool
def query_history_tool(
    query_type: str = "events",
    session_id: str = "",
    limit: int = 10,
) -> str:
    """Query the agent's audit history stored in SQLite.

    query_type options:
      - 'events'       : all recent events (default)
      - 'tools'        : tool calls only
      - 'tool_results' : tool outputs only
      - 'messages'     : user messages only
      - 'responses'    : agent responses only
      - 'blocks'       : guardrail blocks
      - 'confirmations': human-in-the-loop confirmations
      - 'sessions'     : list all sessions (ignores session_id filter)

    session_id: filter to a specific session (empty = current session).
    limit: max number of results to return (default 10, max 100).
    """
    limit = min(max(1, limit), 100)

    if query_type == "sessions":
        rows = list_sessions(settings.audit_db_path)
        if not rows:
            return "No sessions recorded yet."
        lines = ["Sessions:"]
        for r in rows:
            lines.append(
                f"  {r['session_id']} | started {r['started_at'][:19]} | "
                f"{r['interface']} | {r['llm_provider']} | {r['event_count']} events"
            )
        return "\n".join(lines)

    event_type_filter = _EVENT_TYPE_ALIASES.get(query_type, query_type if query_type != "events" else None)
    sid = session_id.strip() or settings.session_id

    rows = query_events(
        settings.audit_db_path,
        session_id=sid,
        event_type=event_type_filter,
        limit=limit,
    )

    if not rows:
        return f"No {query_type} found for session '{sid}'."

    lines = [f"Audit history (session={sid}, type={query_type}, limit={limit}):"]
    for row in reversed(rows):
        lines.append("  " + _fmt_row(row))
    return "\n".join(lines)
