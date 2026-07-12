"""Concurrent execution of per-device work. Stdlib only, unit-testable.

Threads, not asyncio: netmiko is blocking (paramiko), so SSH sessions can
only overlap via threads. The work is I/O-bound, so the GIL is not a factor.
"""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor


def poll_all(
    devices: Sequence[dict],
    poll_fn: Callable[[dict], dict],
    max_workers: int,
) -> list[dict]:
    """Run poll_fn over devices in parallel; results keep input order.

    poll_fn must map failures to result values (never raise), matching
    poll_device's contract of returning a status row for any outcome.
    """
    if not devices:
        return []
    workers = max(1, min(max_workers, len(devices)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(poll_fn, devices))
