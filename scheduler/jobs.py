import queue
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from config import settings

reminder_queue: queue.Queue[str] = queue.Queue()

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


def _fire_reminder(message: str) -> None:
    reminder_queue.put(message)


def schedule_reminder(message: str, run_at: datetime, job_id: str | None = None) -> str:
    sched = get_scheduler()
    job = sched.add_job(
        func=_fire_reminder,
        trigger="date",
        run_date=run_at,
        args=[message],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=300,
    )
    return job.id
