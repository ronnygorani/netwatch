"""Tests for the concurrent poll runner, including the Phase 3 acceptance
check: a simulated 100-device cycle completes well inside one poll interval."""

import time

from runner import poll_all


def test_results_keep_input_order():
    devices = [{"id": n} for n in range(20)]
    results = poll_all(devices, lambda d: {"id": d["id"] * 10}, max_workers=8)
    assert [r["id"] for r in results] == [n * 10 for n in range(20)]


def test_empty_device_list():
    assert poll_all([], lambda d: d, max_workers=10) == []


def test_workers_clamped_to_at_least_one():
    results = poll_all([{"id": 1}], lambda d: d, max_workers=0)
    assert results == [{"id": 1}]


def test_hundred_devices_finish_inside_interval():
    """Serial: 100 devices x 0.05s = 5s. With 10 workers this must take ~0.5s.

    Generous bound (2s) keeps the test stable on slow CI runners while still
    proving parallelism: a serial regression would take 5s and fail.
    """
    devices = [{"id": n} for n in range(100)]

    def slow_poll(device):
        time.sleep(0.05)
        return {"id": device["id"], "status": "up"}

    started = time.monotonic()
    results = poll_all(devices, slow_poll, max_workers=10)
    elapsed = time.monotonic() - started

    assert len(results) == 100
    assert elapsed < 2.0
