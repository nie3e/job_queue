import json
from datetime import datetime, timezone

from sqlalchemy import text

from job_queue.service_layer import unit_of_work


def add_job(
        uow: unit_of_work.UnitOfWork,
        id: int,
        service: str,
        payload: dict,
        priority: int = 0,
        status: str = "pending",
        process_at: datetime = datetime.now(timezone.utc),
        created_at: datetime = datetime.now(timezone.utc),
        modified_at: datetime = datetime.now(timezone.utc),
        reserved_at: datetime | None = None,
        worker_name: str = None,
        attempt_count: int = 0
) -> None:
    sql = """INSERT INTO queue.jobs(
        id, service, payload, priority, status, process_at, created_at,
        modified_at, reserved_at, worker_name, attempt_count
    )
    VALUES (
        :id, :service, :payload, :priority, :status, :process_at, :process_at,
        :created_at, :reserved_at, :worker_name, :attempt_count
    )
    """
    params = dict(
        id=id, service=service, payload=json.dumps(payload), priority=priority,
        status=status, process_at=process_at, created_at=created_at,
        reserved_at=reserved_at, modified_at=modified_at,
        worker_name=worker_name, attempt_count=attempt_count
    )
    with uow:
        uow.session.execute(text(sql), params)
        uow.commit()


def get_job(uow: unit_of_work.UnitOfWork, id: int) -> dict | None:
    sql = """SELECT * FROM queue.jobs WHERE id = :id"""
    params = dict(id=id)
    with uow:
        row = uow.session.execute(text(sql), params).one_or_none()
        uow.commit()

    if not row:
        return None

    return row._mapping  # noqa
