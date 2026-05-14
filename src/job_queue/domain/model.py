from dataclasses import dataclass
from datetime import datetime


@dataclass
class Job:
    id: int
    service: str
    payload: dict
    attempt_count: int
    started_at: datetime
