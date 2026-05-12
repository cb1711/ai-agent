import queue
from dataclasses import dataclass, field
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.interval import IntervalTrigger

from config import settings


@dataclass
class ScheduledTask:
    task_type: str          # "reminder", "agent_prompt", ...
    dest: str               # "cli", "telegram:123", etc.
    payload: dict = field(default_factory=dict)


# Thread-safe bridge from APScheduler background threads to the async event bus.
task_queue: queue.Queue[ScheduledTask] = queue.Queue()

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        jobstores = {
            "default": SQLAlchemyJobStore(url=f"sqlite:///{settings.scheduler_db_path}")
        }
        executors = {"default": ThreadPoolExecutor(max_workers=4)}
        _scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            timezone="UTC",
        )
    return _scheduler


def start_scheduler() -> None:
    sched = get_scheduler()
    if not sched.running:
        sched.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


def _fire_task(task_type: str, dest: str, payload: dict) -> None:
    """Called by APScheduler background thread. Puts task on queue for async pickup."""
    task_queue.put(ScheduledTask(task_type=task_type, dest=dest, payload=payload))


def schedule_task(
    task_type: str,
    payload: dict,
    run_at: datetime,
    dest: str = "cli",
    job_id: str | None = None,
) -> str:
    """Schedule a generic task to fire at run_at."""
    sched = get_scheduler()
    job = sched.add_job(
        func=_fire_task,
        trigger="date",
        run_date=run_at,
        args=[task_type, dest, payload],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=300,
    )
    return job.id


def schedule_recurring_task(
    task_type: str,
    payload: dict,
    interval_hours: float,
    dest: str = "cli",
    job_id: str | None = None,
) -> str:
    """Schedule a task to fire repeatedly every interval_hours."""
    sched = get_scheduler()
    job = sched.add_job(
        func=_fire_task,
        trigger=IntervalTrigger(hours=interval_hours),
        args=[task_type, dest, payload],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=600,
    )
    return job.id


def schedule_reminder(
    message: str, run_at: datetime, job_id: str | None = None, dest: str = "cli"
) -> str:
    """Convenience wrapper: schedule a reminder task."""
    return schedule_task(
        task_type="reminder",
        payload={"message": message},
        run_at=run_at,
        dest=dest,
        job_id=job_id,
    )
