"""Convert UTC log events to model-ready service windows."""

import re
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from statistics import mean

ERROR_LEVELS = {"ERROR", "CRITICAL", "FATAL"}
SIGNAL_LEVELS = ERROR_LEVELS | {"WARN", "WARNING"}
TIMEOUT = re.compile(r"\b(?:timed?\s*out|deadline exceeded)\b", re.I)
DATABASE = re.compile(r"\b(?:database|postgres(?:ql)?|mysql|sql|deadlock|connection pool)\b", re.I)

# The descriptions are also used when explaining unusually large deviations.
FEATURE_DESCRIPTIONS = {
    "event_count": "event volume",
    "error_count": "error count",
    "warning_count": "warning count",
    "critical_count": "critical error count",
    "error_ratio": "error share",
    "unique_errors": "distinct error fingerprints",
    "mean_message_length": "average message length",
    "timeout_count": "timeout mentions",
    "database_error_count": "database-related errors",
    "event_count_delta": "event volume change since the previous window",
    "rolling_event_count": "average event volume across the six preceding windows",
    "rolling_error_count": "average error count across the six preceding windows",
}


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _observations(events: list[dict]) -> dict:
    levels = Counter(event["severity"] for event in events)
    errors = [event for event in events if event["severity"] in ERROR_LEVELS]
    return {
        "event_count": len(events),
        "error_count": len(errors),
        "warning_count": levels["WARN"] + levels["WARNING"],
        "critical_count": levels["CRITICAL"] + levels["FATAL"],
        "error_ratio": len(errors) / max(len(events), 1),
        "unique_errors": len({event["fingerprint"] for event in errors}),
        "mean_message_length": mean(len(event["message"]) for event in events) if events else 0,
        "timeout_count": sum(bool(TIMEOUT.search(event["message"])) for event in events),
        "database_error_count": sum(bool(DATABASE.search(event["message"])) for event in errors),
    }


def service_windows(events: list[dict], minutes: int) -> dict[str, list[dict]]:
    """Build per-service UTC windows, with bounded sampling of long inactive stretches."""
    seconds = minutes * 60
    by_service = defaultdict(lambda: defaultdict(list))
    for event in events:
        epoch = int(timestamp(event["timestamp"]).timestamp() // seconds) * seconds
        by_service[event["service"]][epoch].append(event)

    windows = {}
    for service, buckets in sorted(by_service.items()):
        active = sorted(buckets)
        observed = set(active)
        for before, after in zip(active, active[1:]):
            # Keep the first six empty windows and the window preceding activity.
            # This keeps widely separated historical imports from exploding in size.
            observed.update(range(before + seconds, min(after, before + 7 * seconds), seconds))
            if after - before > seconds:
                observed.add(after - seconds)

        history = deque(maxlen=6)
        windows[service] = []
        previous = None
        for epoch in sorted(observed):
            if previous is not None and epoch - previous > seconds:
                history.clear()
                history.extend([(0, 0)] * 6)
            values = _observations(buckets.get(epoch, []))
            count, errors = values["event_count"], values["error_count"]
            start = datetime.fromtimestamp(epoch, timezone.utc)
            values.update(
                event_count_delta=count - history[-1][0] if history else 0,
                rolling_event_count=mean(item[0] for item in history) if history else 0,
                rolling_error_count=mean(item[1] for item in history) if history else 0,
            )
            windows[service].append({
                "timestamp": start.isoformat(timespec="microseconds").replace("+00:00", "Z"),
                "end": (start + timedelta(minutes=minutes)).isoformat(timespec="microseconds").replace("+00:00", "Z"),
                "features": values,
            })
            history.append((count, errors))
            previous = epoch
    return windows
