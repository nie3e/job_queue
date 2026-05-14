import os
from typing import Any, Generator

import pytest
from sqlalchemy import create_engine, Engine, Connection, text
from sqlalchemy.orm import sessionmaker, Session
from tenacity import retry, stop_after_delay

from testcontainers.postgres import PostgresContainer

dir_path = os.path.dirname(os.path.realpath(__file__))
sql_init_dir = f"{dir_path}/../sql/"


@pytest.fixture(scope="session")
def start_database():
    container = PostgresContainer(
        image="postgres:18",
        username="user",
        password="abc123",
        dbname="test_db"
    )

    container.with_bind_ports("5432/tcp", 5431)
    container.with_volume_mapping(
        host=sql_init_dir,
        container="/docker-entrypoint-initdb.d",
        mode="ro"
    )
    container.start()
    yield container
    container.stop()


@retry(stop=stop_after_delay(10))
def wait_for_postgres_to_come_up(engine: Engine) -> Connection:
    return engine.connect()


@pytest.fixture(scope="session")
def postgres_db() -> Engine:
    engine = create_engine("postgresql://user:abc123@localhost:5431/test_db")
    wait_for_postgres_to_come_up(engine)
    return engine


@pytest.fixture(scope="session")
def psql_session_factory(
        postgres_db
) -> Generator[sessionmaker[Session], Any, None]:
    yield sessionmaker(bind=postgres_db)


@pytest.fixture
def clear_db(psql_session_factory):
    tables = ["queue.jobs"]
    session = psql_session_factory()
    for t in tables:
        session.execute(text(f"DELETE FROM {t}"))
    session.commit()
    session.close()
