import time
import signal
from typing import Any
from types import FrameType
import traceback

from sqlalchemy.orm import sessionmaker

from job_queue.config import logger
from job_queue.domain import model
from job_queue.service_layer.unit_of_work import UnitOfWork


class JobHandler:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name

    def handle(self, job: model.Job | list[model.Job]) -> Any:
        raise NotImplementedError


class WorkerService:
    def __init__(
            self,
            worker_name: str,
            session_factory: sessionmaker,
            handler: JobHandler,
            job_batch: int = 1,
    ):
        self.worker_name = worker_name
        self.session_factory = session_factory
        self.handler = handler
        self.service_name = handler.service_name
        self.job_batch = job_batch
        signal.signal(signal.SIGINT, self._signal_handler)
        logger.info("Worker service created")

    def _signal_handler(self, sig: int, frame: FrameType | None) -> None:
        self._shutdown = True

    def _process_jobs(self) -> int:
        logger.info("Getting job")
        with UnitOfWork(self.session_factory) as uow:
            jobs = uow.jobs.reserve_job(
                service_name=self.service_name,
                worker_name=self.worker_name,
                limit=self.job_batch
            )
            uow.commit()

        if not jobs:
            return 0

        logger.info("Received {} jobs".format(len(jobs)))

        try:
            self.handler.handle(jobs)
            with UnitOfWork(self.session_factory) as uow:
                uow.jobs.finish_job(jobs, self.worker_name)
                uow.commit()
            logger.info("Job finished")
        except Exception:
            error_message = traceback.format_exc()
            logger.error(error_message)
            uow.jobs.fail_job(jobs, self.worker_name, error_message)

        return len(jobs)

    def run(self) -> None:
        while not self._shutdown:
            r = self._process_jobs()
            if not r:
                time.sleep(1)
