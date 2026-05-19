from datetime import datetime
import pytest

from job_queue.domain import model
from job_queue.service_layer import unit_of_work
from common import add_job, get_job

pytestmark = pytest.mark.usefixtures("start_database")


@pytest.mark.usefixtures("clear_db")
def test_uow_reserve_job_empty_queue(psql_session_factory):
    uow = unit_of_work.UnitOfWork(psql_session_factory)

    with uow:
        jobs = uow.jobs.reserve_job(
            service_name="test_service",
            worker_name="pytest",
            limit=1
        )
        uow.commit()

    assert jobs == []


@pytest.mark.usefixtures("clear_db")
def test_uow_reserve_job_returns_jobs(psql_session_factory, sample_jobs):
    uow = unit_of_work.UnitOfWork(psql_session_factory)
    for j in sample_jobs:
        add_job(uow, **j)

    with uow:
        jobs = uow.jobs.reserve_job(
            service_name="test_service",
            worker_name="pytest",
            limit=2
        )
        uow.commit()

    expected_jobs = [
        model.Job(id=10, service="test_service", payload={"workload": "test"},
                  attempt_count=1, started_at=None),  # noqa
        model.Job(id=5, service="test_service", payload={"workload": "test2"},
                  attempt_count=1, started_at=None),  # noqa
    ]

    assert len(jobs) == 2
    jobs[0].started_at = jobs[1].started_at = None
    assert jobs == expected_jobs

    for job_id in [5, 10]:
        job = get_job(uow, job_id)
        assert job
        assert job["status"] == "in_progress"
        assert job["reserved_at"] is not None
        assert job["started_at"] is not None
        assert job["worker_name"] == "pytest"
        assert job["attempt_count"] == 1

    for job_id in [2, 3, 4]:
        job = get_job(uow, job_id)
        assert job
        assert job["status"] == "pending"
        assert job["reserved_at"] is None
        assert job["started_at"] is None
        assert job["worker_name"] is None
        assert job["attempt_count"] == 0


@pytest.mark.usefixtures("clear_db")
def test_uow_reserve_job_attempts_exceeded(psql_session_factory):
    uow = unit_of_work.UnitOfWork(psql_session_factory)
    add_job(
        uow, 10, "test_service", {"a": "b"}, status="failed", attempt_count=5
    )

    with uow:
        jobs = uow.jobs.reserve_job(
            service_name="test_service",
            worker_name="pytest",
            limit=1
        )
        uow.commit()

    assert len(jobs) == 0
    job = get_job(uow, 10)
    assert job
    assert job["status"] == "failed"
    assert job["attempt_count"] == 5
    assert job["reserved_at"] is None


@pytest.mark.usefixtures("clear_db")
def test_uow_finish_job_single_job(psql_session_factory, sample_jobs):
    uow = unit_of_work.UnitOfWork(psql_session_factory)
    for j in sample_jobs:
        add_job(uow, **j)

    with uow:
        jobs = uow.jobs.reserve_job(
            service_name="test_service",
            worker_name="pytest",
            limit=1
        )
        uow.commit()

    job_to_finish = jobs[0]

    with uow:
        result = uow.jobs.finish_job(job_to_finish, worker_name="pytest")
        uow.commit()

    assert result == 1
    job = get_job(uow, 10)
    assert job
    assert job["status"] == "done"
    assert job["reserved_at"] is None
    assert job["finished_at"] is not None
    assert job["worker_name"] is None
    assert job["error_message"] is None

    for job_id in [2, 3, 4, 5]:
        job = get_job(uow, job_id)
        assert job
        assert job["status"] == "pending"
        assert job["reserved_at"] is None
        assert job["finished_at"] is None
        assert job["worker_name"] is None
        assert job["attempt_count"] == 0


@pytest.mark.usefixtures("clear_db")
def test_uow_finish_job_multiple_jobs(psql_session_factory, sample_jobs):
    uow = unit_of_work.UnitOfWork(psql_session_factory)
    for j in sample_jobs:
        add_job(uow, **j)

    with uow:
        jobs = uow.jobs.reserve_job(
            service_name="test_service",
            worker_name="pytest",
            limit=2
        )
        uow.commit()

    with uow:
        result = uow.jobs.finish_job(jobs, worker_name="pytest")
        uow.commit()

    assert result == 2
    for job_id in [5, 10]:
        job = get_job(uow, job_id)
        assert job
        assert job["status"] == "done"
        assert job["reserved_at"] is None
        assert job["finished_at"] is not None
        assert job["worker_name"] is None
        assert job["error_message"] is None

    for job_id in [2, 3, 4]:
        job = get_job(uow, job_id)
        assert job
        assert job["status"] == "pending"
        assert job["reserved_at"] is None
        assert job["finished_at"] is None
        assert job["worker_name"] is None
        assert job["attempt_count"] == 0


@pytest.mark.usefixtures("clear_db")
def test_uow_finish_job_nonexistent_job(psql_session_factory, sample_jobs):
    uow = unit_of_work.UnitOfWork(psql_session_factory)
    for j in sample_jobs:
        add_job(uow, **j)

    nonexistent_job = model.Job(
        id=1234, service="test_service", payload={"a": "b"}, attempt_count=1,
        started_at=datetime.now()
    )

    with uow:
        result = uow.jobs.finish_job(nonexistent_job, worker_name="pytest")
        uow.commit()

    assert result == 0

    for job_id in [2, 3, 4, 5, 10]:
        job = get_job(uow, job_id)
        assert job
        assert job["status"] == "pending"
        assert job["reserved_at"] is None
        assert job["finished_at"] is None
        assert job["worker_name"] is None
        assert job["attempt_count"] == 0


@pytest.mark.usefixtures("clear_db")
def test_uow_fail_job_single_job(psql_session_factory, sample_jobs):
    uow = unit_of_work.UnitOfWork(psql_session_factory)
    for j in sample_jobs:
        add_job(uow, **j)

    with uow:
        jobs = uow.jobs.reserve_job(
            service_name="test_service",
            worker_name="pytest",
            limit=1
        )
        uow.commit()

    job_to_fail = jobs[0]

    with uow:
        result = uow.jobs.fail_job(
            job_to_fail,
            worker_name="pytest",
            error_message="error"
        )
        uow.commit()

    assert result == 1
    job = get_job(uow, 10)
    assert job
    assert job["status"] == "pending"
    assert job["process_at"] > job["modified_at"]
    assert job["reserved_at"] is None
    assert job["finished_at"] is not None
    assert job["worker_name"] is None
    assert job["error_message"] == "error"

    for job_id in [2, 3, 4, 5]:
        job = get_job(uow, job_id)
        assert job
        assert job["status"] == "pending"
        assert job["process_at"] == job["modified_at"]
        assert job["reserved_at"] is None
        assert job["finished_at"] is None
        assert job["worker_name"] is None
        assert job["error_message"] is None
        assert job["attempt_count"] == 0


@pytest.mark.usefixtures("clear_db")
def test_uow_fail_job_multiple_job(psql_session_factory, sample_jobs):
    uow = unit_of_work.UnitOfWork(psql_session_factory)
    for j in sample_jobs:
        add_job(uow, **j)

    with uow:
        jobs = uow.jobs.reserve_job(
            service_name="test_service",
            worker_name="pytest",
            limit=2
        )
        uow.commit()

    with uow:
        result = uow.jobs.fail_job(
            jobs,
            worker_name="pytest",
            error_message="error"
        )
        uow.commit()

    assert result == 2
    for job_id in [5, 10]:
        job = get_job(uow, job_id)
        assert job
        assert job["status"] == "pending"
        assert job["process_at"] > job["modified_at"]
        assert job["reserved_at"] is None
        assert job["finished_at"] is not None
        assert job["worker_name"] is None
        assert job["error_message"] == "error"

    for job_id in [2, 3, 4]:
        job = get_job(uow, job_id)
        assert job
        assert job["status"] == "pending"
        assert job["process_at"] == job["modified_at"]
        assert job["reserved_at"] is None
        assert job["finished_at"] is None
        assert job["worker_name"] is None
        assert job["error_message"] is None
        assert job["attempt_count"] == 0


@pytest.mark.usefixtures("clear_db")
def test_uow_fail_job_nonexistent_job(psql_session_factory, sample_jobs):
    uow = unit_of_work.UnitOfWork(psql_session_factory)
    for j in sample_jobs:
        add_job(uow, **j)

    nonexistent_job = model.Job(
        id=1234, service="test_service", payload={"a": "b"}, attempt_count=1,
        started_at=datetime.now()
    )

    with uow:
        result = uow.jobs.fail_job(
            nonexistent_job,
            worker_name="pytest",
            error_message="error"
        )
        uow.commit()

    assert result == 0

    for job_id in [2, 3, 4, 5, 10]:
        job = get_job(uow, job_id)
        assert job
        assert job["status"] == "pending"
        assert job["process_at"] == job["modified_at"]
        assert job["reserved_at"] is None
        assert job["finished_at"] is None
        assert job["worker_name"] is None
        assert job["error_message"] is None
        assert job["attempt_count"] == 0


@pytest.mark.usefixtures("clear_db")
def test_uow_fail_job_attempts_exceeded_changes_status(psql_session_factory):
    uow = unit_of_work.UnitOfWork(psql_session_factory)
    add_job(
        uow, id=10, service="test_service", payload={"a": "b"},
        status="pending", process_at=datetime(2020, 1, 1), attempt_count=4
    )

    with uow:
        jobs = uow.jobs.reserve_job(
            service_name="test_service",
            worker_name="pytest",
            limit=1
        )
        uow.commit()

    with uow:
        result = uow.jobs.fail_job(
            jobs,
            worker_name="pytest",
            error_message="error"
        )
        uow.commit()

    assert result == 1
    job = get_job(uow, 10)
    assert job
    assert job["status"] == "failed"
    assert job["process_at"] > job["modified_at"]
    assert job["reserved_at"] is None
    assert job["finished_at"] is not None
    assert job["worker_name"] is None
    assert job["error_message"] == "error"


@pytest.mark.usefixtures("clear_db")
def test_uow_sweep_stale_jobs(psql_session_factory):
    uow = unit_of_work.UnitOfWork(psql_session_factory)

    normal_job = {"id": 1, "service": "test_service", "payload": {"a": "b"}}
    not_stale_job = {
        "id": 10, "service": "test_service2", "payload": {"a": "b"},
        "status": "in_progress", "attempt_count": 3, "worker_name": "pytest",
        "reserved_at": datetime.now()
    }
    stale_job = {
        "id": 20, "service": "test_service2", "payload": {"a": "b"},
        "status": "in_progress", "attempt_count": 3, "worker_name": "pytest2",
        "reserved_at": datetime(2020, 1, 1)
    }
    stale_failed_job = {
        "id": 30, "service": "test_service", "payload": {"a": "b"},
        "status": "in_progress", "attempt_count": 5, "worker_name": "pytest3",
        "reserved_at": datetime(2020, 1, 1)
    }
    for job in [normal_job, not_stale_job, stale_job, stale_failed_job]:
        add_job(uow, **job)

    with uow:
        result = uow.jobs.sweep_stale_jobs(stale_after_seconds=3600)
        uow.commit()

    assert result == 2

    job = get_job(uow, 1)
    assert job
    assert job["status"] == "pending"
    assert job["attempt_count"] == 0

    job = get_job(uow, 10)
    assert job
    assert job["status"] == "in_progress"
    assert job["attempt_count"] == 3
    assert job["worker_name"] == "pytest"
    assert job["reserved_at"] is not None

    job = get_job(uow, 20)
    assert job
    assert job["status"] == "pending"
    assert job["attempt_count"] == 2
    assert job["worker_name"] is None
    assert job["reserved_at"] is None

    job = get_job(uow, 30)
    assert job
    assert job["status"] == "failed"
    assert job["attempt_count"] == 5
    assert job["worker_name"] is None
    assert job["reserved_at"] is None
    assert job["finished_at"] is not None
    assert job["error_message"] == "max retries exceeded (worker timeout)"
