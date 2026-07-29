"""Redis-backed job queue (RQ). The API enqueues; the worker executes.

Lazily connected so the API and tests import this module without needing
Redis present.
"""

from functools import lru_cache

from redis import Redis
from rq import Queue

from app.config import settings

QUEUE_NAME = "netwatch"


@lru_cache(maxsize=1)
def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=Redis.from_url(settings.redis_url))


def enqueue_job(job_id: int) -> None:
    """Hand a persisted job's id to the worker. The worker loads the row itself;
    the queue only carries the id, never the payload."""
    get_queue().enqueue("app.jobs.run_job", job_id)
