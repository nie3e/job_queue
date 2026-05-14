from __future__ import annotations
from sqlalchemy.orm import sessionmaker, Session

from job_queue.adapters import repository


class UnitOfWork:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory
        self.session: Session
        self.jobs: repository.JobRepository

    def __enter__(self) -> UnitOfWork:
        self.session = self.session_factory()
        self.jobs = repository.JobRepository(self.session)
        return self

    def __exit__(self, *args) -> None:
        self.rollback()
        self.session.commit()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
