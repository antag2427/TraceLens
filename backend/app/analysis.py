"""Persist a reproducible analysis snapshot and preserve operator decisions."""

from collections import defaultdict

from sqlalchemy import delete, select

from .db import AnalysisRun, Anomaly, Cluster, Incident, IncidentEvent, Log, Preference
from .ingestion import now
from .incidents import dependencies, detect_incidents
from .ml import cluster_errors, detect_anomalies
from .schemas import Settings


def configuration(session):
    row = session.get(Preference, 1)
    return Settings.model_validate(row.value) if row else Settings()


def latest_run(session):
    return session.scalar(select(AnalysisRun).order_by(AnalysisRun.id.desc()).limit(1))


def run_analysis(session):
    settings = configuration(session).model_dump()
    events = [row.as_dict() for row in session.scalars(select(Log).order_by(Log.timestamp, Log.id))]
    anomalies = detect_anomalies(events, settings)
    clusters = cluster_errors(events, settings)
    edges = dependencies(events, settings)
    incidents = detect_incidents(events, anomalies, clusters, edges, settings)
    run = AnalysisRun(
        created_at=now(), event_count=len(events), anomaly_count=sum(a["anomalous"] for a in anomalies),
        cluster_count=len(clusters), incident_count=len(incidents), settings=settings, dependencies=edges,
    )
    session.add(run)
    session.flush()
    session.add_all(Anomaly(run_id=run.id, id=a["id"], service=a["service"], timestamp=a["timestamp"],
                            anomalous=a["anomalous"], details=a) for a in anomalies)
    session.add_all(Cluster(run_id=run.id, id=c["id"], details=c) for c in clusters)

    # Maintain operator state if a later run extends a previously identified incident.
    memberships = defaultdict(set)
    for incident_id, event_id in session.execute(select(IncidentEvent.incident_id, IncidentEvent.event_id)):
        memberships[incident_id].add(event_id)
    previous = {row.id: row for row in session.scalars(select(Incident))}
    exact_matches = {detail["id"] for detail in incidents} & previous.keys()
    claimed = set()
    for detail in incidents:
        proposed_id = detail["id"]
        event_ids = set(detail["event_ids"])
        incident = previous.get(proposed_id)
        if not incident:
            candidates = [
                (len(event_ids & old_ids) / len(event_ids | old_ids), identifier)
                for identifier, old_ids in memberships.items()
                if identifier not in claimed and identifier not in exact_matches and event_ids & old_ids
            ]
            overlap, match = max(candidates, default=(0, ""))
            if overlap >= 0.5:
                incident = previous[match]
        if not incident:
            incident = Incident(id=proposed_id, status="open", notes="")
            session.add(incident)
        claimed.add(incident.id)
        incident.run_id = run.id
        incident.first_seen = detail["first_seen"]
        incident.last_seen = detail["last_seen"]
        incident.severity = detail["severity"]
        incident.details = {**detail, "id": incident.id}
        session.flush()
        session.execute(delete(IncidentEvent).where(IncidentEvent.incident_id == incident.id))
        session.add_all(IncidentEvent(incident_id=incident.id, event_id=identifier) for identifier in event_ids)
    session.commit()
    return run


def incident_json(row, *, detailed=True):
    details = row.details if detailed else {
        field: row.details[field] for field in
        ("id", "title", "description", "severity", "first_seen", "last_seen", "services", "event_count")
    }
    return {**details, "status": row.status, "notes": row.notes}
