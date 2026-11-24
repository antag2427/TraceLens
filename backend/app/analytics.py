"""Aggregate persisted logs and the latest analysis results."""

from collections import defaultdict

from sqlalchemy import case, func, select

from .analysis import incident_json, latest_run
from .db import Anomaly, Incident, Log

ERRORS = ("ERROR", "CRITICAL")
ACTIVE = ("open", "investigating")


def services(session):
    counts = defaultdict(dict)
    for service, severity, count in session.execute(
        select(Log.service, Log.severity, func.count()).group_by(Log.service, Log.severity)
    ):
        counts[service][severity] = count
    run = latest_run(session)
    anomalous = set(session.scalars(select(Anomaly.service).where(
        Anomaly.run_id == run.id, Anomaly.anomalous.is_(True)
    ))) if run else set()
    incidents = defaultdict(list)
    for row in session.scalars(select(Incident)):
        for service in row.details["services"]:
            incidents[service].append(row)
    connected = defaultdict(set)
    for edge in run.dependencies if run else []:
        connected[edge["source"]].add(edge["target"])
        connected[edge["target"]].add(edge["source"])
    items = []
    for service, levels in sorted(counts.items()):
        errors = sum(levels.get(level, 0) for level in ERRORS)
        rows = incidents[service]
        if any(row.severity == "critical" and row.status in ACTIVE for row in rows):
            health = "critical"
        elif service in anomalous:
            health = "anomalous"
        elif errors or levels.get("WARNING"):
            health = "warning"
        else:
            health = "healthy"
        items.append(dict(id=service, name=service, event_count=sum(levels.values()),
                          error_count=errors, anomaly_status=service in anomalous,
                          incident_count=len(rows), health=health, connected_services=sorted(connected[service])))
    return items


def summary(session):
    severity = dict(session.execute(select(Log.severity, func.count()).group_by(Log.severity)).all())
    total = sum(severity.values())
    errors = sum(severity.get(level, 0) for level in ERRORS)
    hour = func.substr(Log.timestamp, 1, 13)
    error_indicator = case((Log.severity.in_(ERRORS), 1), else_=0)
    rows = session.execute(select(hour, func.count(), func.sum(error_indicator)).group_by(hour)
                           .order_by(hour.desc()).limit(168)).all()
    latest = latest_run(session)
    service_health = services(session)
    active = Incident.status.in_(ACTIVE)
    return dict(
        total_events=total, error_rate=errors / total if total else 0,
        active_incidents=session.scalar(select(func.count()).select_from(Incident).where(active)),
        critical_incidents=session.scalar(select(func.count()).select_from(Incident).where(active, Incident.severity == "critical")),
        anomalies=latest.anomaly_count if latest else 0, services=len(service_health),
        recent_incidents=[incident_json(row, detailed=False) for row in session.scalars(
            select(Incident).order_by(Incident.last_seen.desc()).limit(8))],
        volume=[dict(timestamp=f"{bucket}:00:00Z", total=count, errors=int(error_count))
                for bucket, count, error_count in reversed(rows)],
        severity_distribution=severity, service_health=service_health,
    )
