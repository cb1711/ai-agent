import pytest
from config import settings


@pytest.fixture()
def isolated_db(tmp_path, mocker):
    """Patch settings to use a temp DB so each test gets a clean slate."""
    db = str(tmp_path / "test.db")
    mocker.patch.object(settings, "memory_db_path", db)
    mocker.patch.object(settings, "scheduler_db_path", str(tmp_path / "sched.db"))
    return db
