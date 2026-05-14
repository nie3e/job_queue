from abc import ABC, abstractmethod
from datetime import timedelta

from sqlalchemy import func, column, BigInteger, Text, Integer, select
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Session

from job_queue.domain import model


class AbstractRepository(ABC):
    @abstractmethod
    def reserve_job(
            self, service_name: str, worker_name: str, limit: int
    ) -> list[model.Job]:
        raise NotImplementedError

    @abstractmethod
    def finish_job(
            self, job: model.Job | list[model.Job], worker_name: str
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def fail_job(
            self, job: model.Job | list[model.Job], worker_name: str,
            error_message: str
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def sweep_stale_jobs(self, stale_after_seconds: int) -> int:
        raise NotImplementedError


class JobRepository(AbstractRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def reserve_job(
            self, service_name: str, worker_name: str, limit: int
    ) -> list[model.Job]:
        jobs_fn = func.queue.reserve_job(
            service_name, worker_name, limit
        ).table_valued(
            column("id", BigInteger),
            column("service", Text),
            column("payload", JSONB),
            column("attempt_count", Integer),
            column("started_at", TIMESTAMP(timezone=True))
        )
        stmt = select(jobs_fn)

        rows = self.session.execute(stmt)

        jobs = [
            model.Job(**row._mapping)  # noqa
            for row in rows
        ]

        return jobs

    def finish_job(
            self, job: model.Job | list[model.Job], worker_name: str
    ) -> int:
        jobs = [job.id] if not isinstance(job, list) else [j.id for j in job]

        jobs_fn = func.queue.finish_job(
            jobs, worker_name
        )

        stmt = select(jobs_fn)
        row = self.session.execute(stmt).one()

        result = row[0]

        return result

    def fail_job(
            self, job: model.Job | list[model.Job], worker_name: str,
            error_message: str
    ) -> int:
        jobs = [job.id] if not isinstance(job, list) else [j.id for j in job]

        jobs_fn = func.queue.fail_job(
            jobs, worker_name, error_message
        )

        stmt = select(jobs_fn)
        row = self.session.execute(stmt).one()

        result = row[0]

        return result

    def sweep_stale_jobs(self, stale_after_seconds: int) -> int:
        jobs_fn = func.queue.sweep_stale_jobs(
            timedelta(seconds=stale_after_seconds)
        )

        stmt = select(jobs_fn)
        row = self.session.execute(stmt).one()

        result = row[0]

        return result
