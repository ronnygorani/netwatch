"""Parsers for CLI output collected over SSH. Pure stdlib — no netmiko import.

Parsers return None on unrecognized output rather than raising; raw output is
stored server-side for diagnosis. Scheduled for replacement by NAPALM (Phase 4).
"""

import re

# "CPU utilization for five seconds: 7%/0%; one minute: 5%; five minutes: 4%"
# Prefer the five-minute average, then one-minute, then any figure.
_CPU_FIVE_MIN = re.compile(r"five minutes?:\s*(\d+)%", re.IGNORECASE)
_CPU_ONE_MIN = re.compile(r"one minute:\s*(\d+)%", re.IGNORECASE)
_CPU_ANY = re.compile(r"CPU utilization.*?(\d+)%", re.IGNORECASE)

# Two memory formats seen across IOS versions:
#   "... 16809964K total, 6820116K used"          (values before the words)
#   "Processor Pool Total: 856541768 Used: 355836680 Free: ..."  (words before values)
_MEM_K_STYLE = re.compile(r"(\d+)K\s+total.*?(\d+)K\s+used", re.IGNORECASE)
_MEM_POOL_STYLE = re.compile(r"Total:\s*(\d+)\s+Used:\s*(\d+)", re.IGNORECASE)

# "SW-01 uptime is 1 year, 2 weeks, 3 days, 4 hours, 5 minutes"
_UPTIME_UNITS = [
    (re.compile(r"(\d+)\s+year", re.IGNORECASE), 31_536_000),
    (re.compile(r"(\d+)\s+week", re.IGNORECASE), 604_800),
    (re.compile(r"(\d+)\s+day", re.IGNORECASE), 86_400),
    (re.compile(r"(\d+)\s+hour", re.IGNORECASE), 3_600),
    (re.compile(r"(\d+)\s+minute", re.IGNORECASE), 60),
]


def parse_cpu(output: str) -> float | None:
    for pattern in (_CPU_FIVE_MIN, _CPU_ONE_MIN, _CPU_ANY):
        if match := pattern.search(output):
            return float(match.group(1))
    return None


def parse_memory(output: str) -> float | None:
    match = _MEM_K_STYLE.search(output) or _MEM_POOL_STYLE.search(output)
    if not match:
        return None
    total, used = int(match.group(1)), int(match.group(2))
    return round(used / total * 100, 1) if total else None


def parse_uptime_seconds(output: str) -> int | None:
    total = sum(
        int(m.group(1)) * seconds
        for pattern, seconds in _UPTIME_UNITS
        if (m := pattern.search(output))
    )
    return total or None
