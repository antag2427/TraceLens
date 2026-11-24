from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Status(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class StatusChange(BaseModel):
    status: Status
    notes: str | None = Field(default=None, max_length=4000)


class Dependency(BaseModel):
    source: str = Field(min_length=1, max_length=150)
    target: str = Field(min_length=1, max_length=150)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    window_minutes: int = Field(default=5, ge=1, le=180)
    sensitivity: float = Field(default=0.08, ge=0.01, le=0.4)
    incident_gap_minutes: int = Field(default=12, ge=1, le=180)
    min_errors: int = Field(default=4, ge=1, le=200)
    minimum_training_windows: int = Field(default=12, ge=4, le=200)
    isolation_estimators: int = Field(default=100, ge=20, le=300)
    cluster_similarity: float = Field(default=0.26, ge=0.1, le=0.8)
    dependencies: list[Dependency] = Field(default_factory=list, max_length=500)
    root_cause_weights: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_settings(self):
        if any(edge.source == edge.target for edge in self.dependencies):
            raise ValueError("A service cannot depend on itself")
        if any(not 0 <= value <= 10 for value in self.root_cause_weights.values()):
            raise ValueError("Root-cause weights must be between 0 and 10")
        return self


class ImportResult(BaseModel):
    processed: int
    parsed: int
    rejected: int
    duplicates: int
    services: list[str]
    duration_ms: int
    errors: list[dict]


class RunResult(BaseModel):
    id: int
    created_at: str
    event_count: int
    anomaly_count: int
    cluster_count: int
    incident_count: int


Item = TypeVar("Item")


class Page(BaseModel, Generic[Item]):
    items: list[Item]
    total: int
    limit: int
    offset: int


class LogResult(BaseModel):
    id: int
    import_id: int
    timestamp: str
    severity: str
    service: str
    message: str
    normalized_message: str
    fingerprint: str
    trace_id: str | None
    request_id: str | None
    host: str | None
    source_file: str
    metadata: dict
    incident_id: str | None


class AnomalyResult(BaseModel):
    id: str
    timestamp: str
    end: str
    service: str
    score: float
    anomalous: bool
    severity: str
    features: dict[str, float | int]
    explanation: str
    method: str


class ClusterResult(BaseModel):
    id: str
    title: str
    description: str
    count: int
    keywords: list[str]
    messages: list[str]
    severity_distribution: dict[str, int]
    first_seen: str
    last_seen: str
    services: list[str]
    event_ids: list[int]


class IncidentResult(BaseModel):
    id: str
    title: str
    description: str
    severity: str
    first_seen: str
    last_seen: str
    services: list[str]
    event_count: int
    status: Status
    notes: str


class Edge(Dependency):
    kind: str
    evidence: str


class Hypothesis(BaseModel):
    service: str
    pattern: str
    confidence: float
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    temporal_relationship: str
    explanation: str


class TimelineEntry(BaseModel):
    timestamp: str
    service: str
    severity: str
    message: str
    kind: str
    event_id: int | None = None
    trace_id: str | None = None
    request_id: str | None = None


class Investigation(IncidentResult):
    event_ids: list[int]
    anomalies: list[AnomalyResult]
    clusters: list[ClusterResult]
    timeline: list[TimelineEntry]
    hypotheses: list[Hypothesis]
    dependencies: list[Edge]


class ServiceResult(BaseModel):
    id: str
    name: str
    event_count: int
    error_count: int
    anomaly_status: bool
    incident_count: int
    health: str
    connected_services: list[str]


class DatasetResult(BaseModel):
    id: int
    source_file: str
    created_at: str
    result: ImportResult


class VolumeBucket(BaseModel):
    timestamp: str
    total: int
    errors: int


class SummaryResult(BaseModel):
    total_events: int
    active_incidents: int
    critical_incidents: int
    anomalies: int
    services: int
    error_rate: float
    recent_incidents: list[IncidentResult]
    volume: list[VolumeBucket]
    severity_distribution: dict[str, int]
    service_health: list[ServiceResult]
