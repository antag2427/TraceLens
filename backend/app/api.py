"""Versioned HTTP API."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session as DatabaseSession

from .analysis import configuration, incident_json, latest_run, run_analysis
from .analytics import services, summary
from .db import AnalysisRun, Anomaly, Cluster, Import, Incident, IncidentEvent, Log, Preference
from .ingestion import extension, ingest, safe_name, utc
from .reports import build_report, markdown
from .schemas import (
    AnomalyResult, ClusterResult, DatasetResult, Edge, ImportResult, IncidentResult,
    Investigation, LogResult, Page, RunResult, ServiceResult, Settings, Status, StatusChange,
    SummaryResult,
)

router = APIRouter(prefix="/api/v1")
Limit = Annotated[int, Query(ge=1, le=1000)]
Offset = Annotated[int, Query(ge=0)]
Severity = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
IncidentSeverity = Literal["critical", "high", "medium", "low"]


def session_for(request: Request):
    with request.app.state.sessions() as session:
        yield session


Session = Annotated[DatabaseSession, Depends(session_for)]


def paginated(session, statement, transform, limit, offset):
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    items = [transform(row) for row in session.scalars(statement.offset(offset).limit(limit))]
    return dict(items=items, total=total, limit=limit, offset=offset)


def scoped(statement, conditions):
    return statement.where(*(column == value for column, value in conditions if value is not None))


def period(statement, column, start, end):
    if start is not None:
        statement = statement.where(column >= utc(start))
    if end is not None:
        statement = statement.where(column <= utc(end))
    return statement


def require(session, model, identifier):
    row = session.get(model, identifier)
    if row is None:
        raise HTTPException(404, "Record not found")
    return row


def serialize_logs(session, logs):
    identifiers = [row.id for row in logs]
    associations = {}
    if identifiers:
        statement = (select(IncidentEvent.event_id, IncidentEvent.incident_id)
                     .join(Incident).where(IncidentEvent.event_id.in_(identifiers))
                     .order_by(Incident.run_id, Incident.id))
        associations = dict(session.execute(statement).all())
    payload = []
    for row in logs:
        record = row.as_dict()
        record["metadata"] = record.pop("attributes")
        record.pop("dedup_key")
        payload.append({**record, "incident_id": associations.get(row.id)})
    return payload


@router.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


@router.get("/analytics/summary", response_model=SummaryResult, tags=["System"])
def analytics(session: Session):
    return summary(session)


@router.post("/logs/upload", response_model=ImportResult, tags=["Logs"])
def upload(file: UploadFile, request: Request, session: Session):
    name = safe_name(file.filename or "")
    try:
        extension(name)
    except ValueError as exc:
        raise HTTPException(415, str(exc)) from exc
    if (file.size or 0) > request.app.state.max_upload:
        raise HTTPException(413, "Log file exceeds the configured upload limit")
    if not file.size:
        raise HTTPException(400, "The file is empty")
    sample = file.file.read(4096)
    file.file.seek(0)
    if b"\x00" in sample:
        raise HTTPException(415, "Upload must contain UTF-8 text")
    return ingest(session, file.file, name)


@router.post("/logs/demo", response_model=ImportResult, tags=["Logs"])
def demo(request: Request, session: Session):
    path = request.app.state.demo_file
    if not path.is_file():
        raise HTTPException(503, "Demonstration dataset is unavailable")
    with path.open("rb") as source:
        return ingest(session, source, path.name)


@router.get("/logs", response_model=Page[LogResult], tags=["Logs"])
def logs(session: Session, q: Annotated[str | None, Query(max_length=250)] = None,
         service: str | None = None, severity: Severity | None = None, trace_id: str | None = None,
         request_id: str | None = None, start: datetime | None = None, end: datetime | None = None,
         limit: Limit = 50, offset: Offset = 0, sort: Literal["asc", "desc"] = "desc"):
    statement = scoped(select(Log), ((Log.service, service), (Log.severity, severity),
                                      (Log.trace_id, trace_id), (Log.request_id, request_id)))
    if q:
        statement = statement.where(or_(Log.message.icontains(q, autoescape=True),
                                        Log.service.icontains(q, autoescape=True)))
    statement = period(statement, Log.timestamp, start, end)
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    order = (Log.timestamp, Log.id) if sort == "asc" else (Log.timestamp.desc(), Log.id.desc())
    items = serialize_logs(session, list(session.scalars(statement.order_by(*order).offset(offset).limit(limit))))
    return dict(items=items, total=total, limit=limit, offset=offset)


@router.get("/logs/{log_id}", response_model=LogResult, tags=["Logs"])
def log(log_id: int, session: Session):
    return serialize_logs(session, [require(session, Log, log_id)])[0]


@router.get("/incidents", response_model=Page[IncidentResult], tags=["Incidents"])
def incidents(session: Session, service: str | None = None, severity: IncidentSeverity | None = None,
              status: Status | None = None, start: datetime | None = None, end: datetime | None = None,
              limit: Limit = 50, offset: Offset = 0):
    statement = scoped(select(Incident), ((Incident.severity, severity), (Incident.status, status)))
    if service:
        members = func.json_each(Incident.details, "$.services").table_valued("value")
        statement = statement.where(select(1).select_from(members).where(members.c.value == service).exists())
    statement = period(statement, Incident.first_seen, start, end)
    return paginated(session, statement.order_by(Incident.first_seen.desc(), Incident.id),
                     lambda row: incident_json(row, detailed=False), limit, offset)


@router.get("/incidents/{incident_id}", response_model=Investigation, response_model_exclude_unset=True, tags=["Incidents"])
def incident(incident_id: str, session: Session):
    return incident_json(require(session, Incident, incident_id))


@router.patch("/incidents/{incident_id}/status", response_model=Investigation, response_model_exclude_unset=True, tags=["Incidents"])
def update_status(incident_id: str, change: StatusChange, session: Session):
    row = require(session, Incident, incident_id)
    row.status = change.status.value
    if change.notes is not None:
        row.notes = change.notes
    session.commit()
    return incident_json(row)


@router.post("/analysis/run", response_model=RunResult, tags=["Analysis"])
def analysis(request: Request, session: Session):
    lock = request.app.state.analysis_lock
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "An analysis is already running")
    try:
        return run_analysis(session).as_dict()
    finally:
        lock.release()


@router.get("/analysis/runs", response_model=list[RunResult], tags=["Analysis"])
def runs(session: Session, limit: Limit = 50, offset: Offset = 0):
    return [row.as_dict() for row in session.scalars(select(AnalysisRun)
                    .order_by(AnalysisRun.id.desc()).limit(limit).offset(offset))]


@router.get("/anomalies", response_model=Page[AnomalyResult], tags=["Analysis"])
def anomalies(session: Session, service: str | None = None, anomalous: bool | None = None,
              limit: Limit = 100, offset: Offset = 0):
    run = latest_run(session)
    statement = scoped(select(Anomaly).where(Anomaly.run_id == (run.id if run else 0)),
                       ((Anomaly.service, service), (Anomaly.anomalous, anomalous)))
    statement = statement.order_by(Anomaly.timestamp.desc(), Anomaly.service)
    return paginated(session, statement, lambda row: row.details, limit, offset)


@router.get("/clusters", response_model=Page[ClusterResult], tags=["Analysis"])
def clusters(session: Session, limit: Limit = 100, offset: Offset = 0):
    run = latest_run(session)
    statement = select(Cluster).where(Cluster.run_id == (run.id if run else 0)).order_by(Cluster.id)
    return paginated(session, statement, lambda row: row.details, limit, offset)


@router.get("/services", response_model=list[ServiceResult], tags=["Services"])
def list_services(session: Session):
    return services(session)


@router.get("/services/dependencies", response_model=list[Edge], tags=["Services"])
def dependency_graph(session: Session):
    run = latest_run(session)
    return run.dependencies if run else []


@router.get("/services/{service_id}", response_model=ServiceResult, tags=["Services"])
def service(service_id: str, session: Session):
    for item in services(session):
        if item["id"] == service_id:
            return item
    raise HTTPException(404, "Service not found")


@router.get("/reports/{incident_id}/markdown", tags=["Reports"], response_class=Response)
def markdown_report(incident_id: str, session: Session):
    report = build_report(incident_json(require(session, Incident, incident_id)))
    return Response(markdown(report), media_type="text/markdown",
                    headers={"Content-Disposition": f'attachment; filename="incident-{incident_id}.md"'})


@router.get("/reports/{incident_id}/json", tags=["Reports"])
def json_report(incident_id: str, session: Session):
    report = build_report(incident_json(require(session, Incident, incident_id)))
    return JSONResponse(report, headers={"Content-Disposition": f'attachment; filename="incident-{incident_id}.json"'})


@router.get("/settings", response_model=Settings, tags=["Settings"])
def settings(session: Session):
    return configuration(session)


@router.put("/settings", response_model=Settings, tags=["Settings"])
def save_settings(value: Settings, session: Session):
    data = value.model_dump()
    statement = insert(Preference).values(id=1, value=data)
    session.execute(statement.on_conflict_do_update(index_elements=["id"], set_={"value": data}))
    session.commit()
    return value


@router.get("/datasets", response_model=list[DatasetResult], tags=["Settings"])
def datasets(session: Session, limit: Limit = 50, offset: Offset = 0):
    return [row.as_dict() for row in session.scalars(select(Import).order_by(Import.id.desc())
                                                     .limit(limit).offset(offset))]
