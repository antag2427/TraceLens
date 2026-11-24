from pathlib import Path

from sqlalchemy import JSON, ForeignKey, Index, String, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    def as_dict(self):
        return {attribute.key: getattr(self, attribute.key)
                for attribute in self.__mapper__.column_attrs}


class Import(Base):
    __tablename__ = "imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_file: Mapped[str]
    created_at: Mapped[str]
    result: Mapped[dict] = mapped_column(JSON)


class Log(Base):
    __tablename__ = "logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[str] = mapped_column(String(27), index=True)
    service: Mapped[str] = mapped_column(index=True)
    severity: Mapped[str] = mapped_column(index=True)
    message: Mapped[str]
    normalized_message: Mapped[str]
    fingerprint: Mapped[str] = mapped_column(index=True)
    dedup_key: Mapped[str] = mapped_column(unique=True)
    trace_id: Mapped[str | None] = mapped_column(index=True)
    request_id: Mapped[str | None] = mapped_column(index=True)
    host: Mapped[str | None]
    source_file: Mapped[str]
    attributes: Mapped[dict] = mapped_column(JSON)
    import_id: Mapped[int] = mapped_column(ForeignKey("imports.id"), index=True)
    __table_args__ = (Index("ix_log_service_time", "service", "timestamp"),)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[str]
    event_count: Mapped[int]
    anomaly_count: Mapped[int]
    cluster_count: Mapped[int]
    incident_count: Mapped[int]
    settings: Mapped[dict] = mapped_column(JSON)
    dependencies: Mapped[list] = mapped_column(JSON)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    first_seen: Mapped[str] = mapped_column(index=True)
    last_seen: Mapped[str]
    severity: Mapped[str] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(default="open", index=True)
    notes: Mapped[str] = mapped_column(default="")
    details: Mapped[dict] = mapped_column(JSON)


class IncidentEvent(Base):
    __tablename__ = "incident_events"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("logs.id"), primary_key=True, index=True)


class Anomaly(Base):
    __tablename__ = "anomalies"
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    timestamp: Mapped[str] = mapped_column(index=True)
    service: Mapped[str] = mapped_column(index=True)
    anomalous: Mapped[bool]
    details: Mapped[dict] = mapped_column(JSON)


class Cluster(Base):
    __tablename__ = "clusters"
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    details: Mapped[dict] = mapped_column(JSON)


class Preference(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite", database=str(path)), connect_args={"timeout": 30})

    @event.listens_for(engine, "connect")
    def sqlite_pragmas(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")

    return engine, sessionmaker(engine, expire_on_commit=False)
