from typing import Any

import pytest

from job_queue.domain import model
from job_queue.service_layer import unit_of_work
from job_queue.service_layer.worker import WorkerService, JobHandler
from tests.common import add_job

pytestmark = pytest.mark.usefixtures("start_database")


class ReverseHandler(JobHandler):
    def handle(self, job: model.Job | list[model.Job]) -> Any:
        return 0


@pytest.mark.usefixtures("clear_db")
def test_worker_service_process_job(psql_session_factory, sample_jobs):
    uow = unit_of_work.UnitOfWork(psql_session_factory)
    for j in sample_jobs:
        add_job(uow, **j)

    handler = ReverseHandler(service_name="test_service")
    worker = WorkerService(
        worker_name="test_worker",
        session_factory=psql_session_factory,
        handler=handler,
        job_batch=2
    )

    r = worker._process_jobs()

    assert r == 2
