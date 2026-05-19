from typing import Any

import pytest

from job_queue.domain import model
from job_queue.service_layer import unit_of_work
from job_queue.service_layer.worker import WorkerService, JobHandler
from common import add_job

pytestmark = pytest.mark.usefixtures("start_database")


class ReverseHandler(JobHandler):
    def __init__(self, service_name: str) -> None:
        super().__init__(service_name)
        self.results = []

    def handle(self, job: model.Job | list[model.Job]) -> Any:
        jobs = (
            [job.payload]
            if not isinstance(job, list)
            else [j.payload for j in job]
        )

        reverse = [j["text"][::-1] for j in jobs]
        self.results.extend(reverse)


@pytest.mark.usefixtures("clear_db")
def test_worker_e2e_process(psql_session_factory):
    uow = unit_of_work.UnitOfWork(psql_session_factory)
    for i in range(10):
        add_job(
            uow,
            id=i,
            service="test_service" if i < 5 else "test_service2",
            payload={"text": f"sample_{i}", "extra": "value"}
        )

    handler = ReverseHandler(service_name="test_service")
    worker = WorkerService(
        worker_name="test_worker",
        session_factory=psql_session_factory,
        handler=handler,
        job_batch=2
    )

    while worker._process_jobs():
        pass

    expected_results = {
        "0_elpmas", "1_elpmas", "2_elpmas", "3_elpmas", "4_elpmas"
    }

    assert len(handler.results) == 5
    assert set(handler.results) == expected_results
