from datetime import datetime

import pytest


@pytest.fixture
def sample_jobs() -> list[dict]:
    jobs = [
        {
            "id": 10,
            "service": "test_service",
            "payload": {"workload": "test"},
            "priority": 10,
            "process_at": datetime(2020, 1, 1),
            "created_at": datetime(2020, 1, 1),
            "modified_at": datetime(2020, 1, 1),
        },
        {
            "id": 5,
            "service": "test_service",
            "payload": {"workload": "test2"},
            "priority": 0,
            "process_at": datetime(2019, 1, 1),
            "created_at": datetime(2019, 1, 1),
            "modified_at": datetime(2019, 1, 1),
        },
        {
            "id": 4,
            "service": "test_service",
            "payload": {"workload": "test3"},
            "priority": 0,
            "process_at": datetime(2020, 1, 1),
            "created_at": datetime(2020, 1, 1),
            "modified_at": datetime(2020, 1, 1),
        },
        {
            "id": 3,
            "service": "test_service_2",
            "payload": {"workload": "test_21"},
            "priority": 0,
            "process_at": datetime(2020, 1, 1),
            "created_at": datetime(2020, 1, 1),
            "modified_at": datetime(2020, 1, 1),
        },
        {
            "id": 2,
            "service": "test_service_2",
            "payload": {"workload": "test_22"},
            "priority": 0,
            "process_at": datetime(2020, 1, 1),
            "created_at": datetime(2020, 1, 1),
            "modified_at": datetime(2020, 1, 1),
        },
    ]
    return jobs
