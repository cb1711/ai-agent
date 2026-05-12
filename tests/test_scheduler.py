import time
from datetime import datetime, timezone, timedelta

import pytest
from apscheduler.schedulers.background import BackgroundScheduler


class TestSchedulerLifecycle:
    def test_get_scheduler_returns_background_scheduler(self, isolated_db):
        from scheduler.jobs import get_scheduler
        import scheduler.jobs as jobs
        jobs._scheduler = None  # reset singleton for isolation
        sched = get_scheduler()
        assert isinstance(sched, BackgroundScheduler)

    def test_start_and_stop(self, isolated_db):
        import scheduler.jobs as jobs
        jobs._scheduler = None
        jobs.start_scheduler()
        assert jobs.get_scheduler().running
        jobs.stop_scheduler()
        assert not jobs.get_scheduler().running
        jobs._scheduler = None

    def test_double_start_is_safe(self, isolated_db):
        import scheduler.jobs as jobs
        jobs._scheduler = None
        jobs.start_scheduler()
        jobs.start_scheduler()  # should not raise
        jobs.stop_scheduler()
        jobs._scheduler = None


class TestScheduledTasks:
    def test_fire_task_puts_scheduled_task_on_queue(self):
        from scheduler.jobs import _fire_task, task_queue, ScheduledTask
        while not task_queue.empty():
            task_queue.get_nowait()

        _fire_task("reminder", "cli", {"message": "wake up!"})

        assert not task_queue.empty()
        task = task_queue.get_nowait()
        assert isinstance(task, ScheduledTask)
        assert task.task_type == "reminder"
        assert task.dest == "cli"
        assert task.payload == {"message": "wake up!"}

    def test_fire_task_agent_prompt(self):
        from scheduler.jobs import _fire_task, task_queue
        while not task_queue.empty():
            task_queue.get_nowait()

        _fire_task("agent_prompt", "cli", {"prompt": "summarise the news"})

        task = task_queue.get_nowait()
        assert task.task_type == "agent_prompt"
        assert task.payload["prompt"] == "summarise the news"

    def test_schedule_reminder_adds_job(self, isolated_db):
        import scheduler.jobs as jobs
        jobs._scheduler = None
        jobs.start_scheduler()
        try:
            run_at = datetime.now(timezone.utc) + timedelta(hours=1)
            job_id = jobs.schedule_reminder("test message", run_at)
            assert job_id is not None
            assert jobs.get_scheduler().get_job(job_id) is not None
        finally:
            jobs.stop_scheduler()
            jobs._scheduler = None

    def test_schedule_task_adds_job(self, isolated_db):
        import scheduler.jobs as jobs
        jobs._scheduler = None
        jobs.start_scheduler()
        try:
            run_at = datetime.now(timezone.utc) + timedelta(hours=1)
            job_id = jobs.schedule_task(
                task_type="agent_prompt",
                payload={"prompt": "check the weather"},
                run_at=run_at,
            )
            assert job_id is not None
            assert jobs.get_scheduler().get_job(job_id) is not None
        finally:
            jobs.stop_scheduler()
            jobs._scheduler = None

    def test_reminder_fires_and_reaches_queue(self, isolated_db):
        import scheduler.jobs as jobs
        jobs._scheduler = None
        jobs.start_scheduler()
        try:
            while not jobs.task_queue.empty():
                jobs.task_queue.get_nowait()

            run_at = datetime.now(timezone.utc) + timedelta(seconds=1)
            jobs.schedule_reminder("integration test reminder", run_at, dest="cli")

            for _ in range(50):
                if not jobs.task_queue.empty():
                    break
                time.sleep(0.1)

            assert not jobs.task_queue.empty()
            task = jobs.task_queue.get_nowait()
            assert task.task_type == "reminder"
            assert task.payload["message"] == "integration test reminder"
            assert task.dest == "cli"
        finally:
            jobs.stop_scheduler()
            jobs._scheduler = None

    def test_replace_existing_job_with_same_id(self, isolated_db):
        import scheduler.jobs as jobs
        jobs._scheduler = None
        jobs.start_scheduler()
        try:
            run_at = datetime.now(timezone.utc) + timedelta(hours=2)
            jobs.schedule_reminder("first", run_at, job_id="dedup-test")
            jobs.schedule_reminder("second", run_at, job_id="dedup-test")
            assert len([j for j in jobs.get_scheduler().get_jobs() if j.id == "dedup-test"]) == 1
        finally:
            jobs.stop_scheduler()
            jobs._scheduler = None
