from langchain_core.tools import tool

from scheduler.jobs import get_scheduler, schedule_recurring_task

_JOB_ID = "self_reflection_recurring"

_SELF_REFLECT_PROMPT = (
    "Perform a self-reflection cycle: "
    "1) Use analyze_agent_performance to review recent patterns. "
    "2) Use get_current_system_prompt to review the current guidelines. "
    "3) If you identify clear, concrete improvements, use update_system_prompt or "
    "create_new_tool with your proposed changes — each requires your approval. "
    "4) Summarize what you found and what (if anything) you changed."
)


@tool
def configure_self_reflection(interval_hours: float = 24.0) -> str:
    """Schedule or disable periodic self-reflection. The agent will automatically analyze
    its audit logs and propose improvements on the given interval.
    interval_hours: how often to run (default 24). Pass 0 or less to disable."""
    try:
        sched = get_scheduler()
        if interval_hours <= 0:
            try:
                sched.remove_job(_JOB_ID)
                return "Self-reflection schedule disabled."
            except Exception:
                return "Self-reflection was not scheduled."

        schedule_recurring_task(
            task_type="agent_prompt",
            payload={"prompt": _SELF_REFLECT_PROMPT},
            interval_hours=interval_hours,
            dest="cli",
            job_id=_JOB_ID,
        )
        return (
            f"Self-reflection scheduled every {interval_hours}h (job id: {_JOB_ID}). "
            f"Pass interval_hours=0 to disable."
        )
    except Exception as e:
        return f"Error configuring self-reflection: {e}"
