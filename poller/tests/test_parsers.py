"""Table-driven tests for the CLI output parsers.

Inputs are realistic captures of Cisco IOS output formats. When Phase 4 adds
the lab, captures from real cEOS/IOS devices should be appended here — every
parsing bug found in the field becomes a regression case.
"""

import pytest
from parsers import metrics_from_napalm, parse_cpu, parse_memory, parse_uptime_seconds


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        # Standard IOS: prefer the five-minute average
        ("CPU utilization for five seconds: 7%/0%; one minute: 5%; five minutes: 4%", 4.0),
        # Only a one-minute figure present
        ("CPU utilization for five seconds: 9%/1%; one minute: 6%", 6.0),
        # Fallback: any utilization figure
        ("CPU utilization: 12%", 12.0),
        # Case variations happen across platforms
        ("cpu utilization for five seconds: 3%/0%; one minute: 2%; FIVE MINUTES: 1%", 1.0),
        # Garbage / empty → None, never an exception
        ("% Invalid input detected at '^' marker.", None),
        ("", None),
    ],
)
def test_parse_cpu(output, expected):
    assert parse_cpu(output) == expected


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        # "K-style": values before the words
        ("Processor memory: 16809964K total, 6820116K used", 40.6),
        # "Pool-style": words before the values (bytes)
        ("Processor Pool Total: 856541768 Used: 214135442 Free: 642406326", 25.0),
        # Zero total must not divide by zero
        ("0K total, 0K used", None),
        ("nothing recognizable", None),
        ("", None),
    ],
)
def test_parse_memory(output, expected):
    assert parse_memory(output) == expected


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("SW-01 uptime is 3 days, 4 hours, 5 minutes", 3 * 86400 + 4 * 3600 + 5 * 60),
        # Years and weeks must count (the old parser dropped them entirely)
        (
            "core-sw uptime is 1 year, 2 weeks, 3 days, 4 hours, 5 minutes",
            31_536_000 + 2 * 604_800 + 3 * 86400 + 4 * 3600 + 5 * 60,
        ),
        ("uptime is 45 minutes", 45 * 60),
        ("uptime is 1 hour, 1 minute", 3660),
        # No recognizable duration → None
        ("SW-01 uptime is unknown", None),
        ("", None),
    ],
)
def test_parse_uptime_seconds(output, expected):
    assert parse_uptime_seconds(output) == expected


def test_metrics_from_napalm_full_data():
    """Typical NAPALM getter shapes (as returned by the eos driver)."""
    facts = {"uptime": 3605.4, "vendor": "Arista", "hostname": "leaf1"}
    environment = {
        "cpu": {0: {"%usage": 4.0}, 1: {"%usage": 6.0}},
        "memory": {"available_ram": 4_000_000, "used_ram": 1_000_000},
    }
    result = metrics_from_napalm(facts, environment)
    assert result == {"cpu_percent": 5.0, "memory_percent": 25.0, "uptime_seconds": 3605}


def test_metrics_from_napalm_missing_sensors():
    """Virtual platforms often lack environment data; uptime must survive."""
    result = metrics_from_napalm({"uptime": 120}, {})
    assert result == {"cpu_percent": None, "memory_percent": None, "uptime_seconds": 120}


def test_metrics_from_napalm_empty_everything():
    result = metrics_from_napalm({}, {})
    assert result == {"cpu_percent": None, "memory_percent": None, "uptime_seconds": None}


def test_metrics_from_napalm_zero_available_ram_no_crash():
    result = metrics_from_napalm({}, {"memory": {"available_ram": 0, "used_ram": 0}})
    assert result["memory_percent"] is None
