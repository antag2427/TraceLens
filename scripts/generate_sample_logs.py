"""Generate repeatable microservice traffic with a trace-linked failure cascade."""

import argparse
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = {
    "api-gateway": ("Routed HTTP request", "Response cache miss"),
    "authentication": ("Validated session", "Token nearing expiry"),
    "checkout": ("Calculated order total", "Cart refresh required"),
    "payment": ("Authorized card transaction", "Payment retry scheduled"),
    "inventory": ("Reserved stock units", "Inventory near reorder threshold"),
    "notification": ("Queued delivery receipt", "Delivery provider rate limit"),
    "database": ("Completed query in", "Connection pool utilization elevated"),
}
START = datetime(2025, 3, 18, 8, tzinfo=UTC)


def generate():
    rng = random.Random(8712)
    events = []

    def add(offset, service, severity, message, trace=None, **metadata):
        events.append(dict(
            timestamp=(START + timedelta(seconds=offset)).isoformat(),
            service=service, severity=severity, message=message, trace_id=trace,
            request_id=f"req-{trace}" if trace else None,
            host=f"{service}-{rng.randint(1, 3)}", region="eu-west-1", **metadata,
        ))

    for minute in range(240):
        for service, (normal, warning) in SERVICES.items():
            if service == "notification" and 60 <= minute < 75:
                continue
            for _ in range(rng.randint(2, 4)):
                choice = rng.random()
                level, message = ("WARNING", warning) if choice < .035 else ("INFO", normal)
                add(minute * 60 + rng.randint(0, 58), service, level,
                    f"{message} {rng.randint(10, 9999)}", latency_ms=rng.randint(8, 135))

    onset = 150 * 60
    add(onset - 90, "database", "WARNING", "Connection pool wait time increasing")
    stages = [
        (0, "database", "CRITICAL", "Database connection pool exhausted after timeout"),
        (70, "payment", "ERROR", "Payment database transaction timed out"),
        (140, "checkout", "ERROR", "Checkout payment authorization failed"),
        (210, "api-gateway", "ERROR", "Upstream checkout returned 503"),
    ]
    for sequence in range(42):
        for delay, service, level, message in stages:
            add(onset + sequence * 8 + delay, service, level, f"{message} for order {4100 + sequence}",
                f"cascade-{sequence:03}", latency_ms=3000 + sequence * 15)
    for delay, service, _, _ in stages:
        add(onset + 640 + delay // 2, service, "INFO", "Service recovered after successful health check")
    for sequence in range(6):
        add(195 * 60 + sequence * 12, "inventory", "ERROR", f"Stock reconciliation failed for item {8200 + sequence}")
    return sorted(events, key=lambda event: (event["timestamp"], event["service"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/generated/demo.jsonl")
    destination = parser.parse_args().output
    destination.parent.mkdir(parents=True, exist_ok=True)
    events = generate()
    with destination.open("w", encoding="utf-8", newline="\n") as stream:
        for event in events:
            stream.write(json.dumps(event, separators=(",", ":")) + "\n")
    print(f"Wrote {len(events)} events to {destination}")
