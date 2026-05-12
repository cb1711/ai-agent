from datetime import datetime, timezone
import dateutil.parser
from langchain_core.tools import tool

from scheduler.jobs import schedule_reminder


@tool
def schedule_reminder_tool(message: str, when: str) -> str:
    """Schedule a reminder to appear in the terminal at a future time.
    'message': the reminder text to display.
    'when': ISO 8601 datetime string, e.g. '2026-05-05T15:30:00+05:30'.
    If no timezone is given, UTC is assumed. Time must be in the future."""
    try:
        run_at = dateutil.parser.parse(when)
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        if run_at <= now:
            return "Error: scheduled time must be in the future."

        job_id = schedule_reminder(message=message, run_at=run_at, dest="cli")
        return f"Reminder scheduled for {run_at.isoformat()} (job id: {job_id})"
    except Exception as e:
        return f"Failed to schedule reminder: {e}"
