import time
import queue
from datetime import datetime, timezone, timedelta

import pytest
from apscheduler.schedulers.background import BackgroundScheduler


class TestSchedulerLifecycle:
    def test_get_scheduler_returns_background_scheduler(self, isolated_db):
        from scheduler.jobs import get_scheduler, _scheduler
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


class TestReminderJobs:
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

    def test_fire_reminder_puts_message_on_queue(self):
        from scheduler.jobs import _fire_reminder, reminder_queue
        # drain any existing items
        while not reminder_queue.empty():
            reminder_queue.get_nowait()

        _fire_reminder("wake up!")
        assert not reminder_queue.empty()
        assert reminder_queue.get_nowait() == "wake up!"

    def test_reminder_fires_and_reaches_queue(self, isolated_db):
        import scheduler.jobs as jobs
        jobs._scheduler = None
        jobs.start_scheduler()
        try:
            # drain queue
            while not jobs.reminder_queue.empty():
                jobs.reminder_queue.get_nowait()

            run_at = datetime.now(timezone.utc) + timedelta(seconds=1)
            jobs.schedule_reminder("integration test reminder", run_at)

            # wait up to 5 seconds for the job to fire
            for _ in range(50):
                if not jobs.reminder_queue.empty():
                    break
                time.sleep(0.1)

            assert not jobs.reminder_queue.empty()
            msg = jobs.reminder_queue.get_nowait()
            assert msg == "integration test reminder"
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
            # replace_existing=True means there's still exactly one job with that id
            assert len([j for j in jobs.get_scheduler().get_jobs() if j.id == "dedup-test"]) == 1
        finally:
            jobs.stop_scheduler()
            jobs._scheduler = None
