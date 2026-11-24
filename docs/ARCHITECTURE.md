# Architecture

TraceLens has two processes. React renders the operational workspace and FastAPI exposes typed HTTP operations. Under Compose, Nginx serves the Vite build and forwards API and documentation requests to the backend over the internal network. The backend persists operational state in one SQLite file.

| Boundary | Implementation | Responsibility |
| --- | --- | --- |
| Startup and HTTP | `backend/app/main.py`, `api.py`, `schemas.py` | App setup, validation, serialization, routes and integration |
| Persistence | `backend/app/db.py` | SQLAlchemy models, database connections and schema initialization |
| Ingestion | `backend/app/ingestion.py` | File parsing, message handling, UTC normalization, deduplication and feedback |
| Analysis | `backend/app/analysis.py`, `features.py`, `ml.py` | Execute the pipeline, build window features, score unusual activity and group errors |
| Investigation | `backend/app/incidents.py` | Correlation, hypotheses, service evidence and incident timelines |
| Export | `backend/app/reports.py` | Markdown and JSON investigation artifacts |
| Presentation | `frontend/src/` | Routes and views, API calls, controls, charts and investigation details |

## Write and read paths

1. An upload enters the ingestion boundary as an untrusted file. The parser reads supported formats, validates values and preserves issues for the upload result.
2. Each normalized event contains a UTC timestamp, severity, service, original message after handling, normalized message, fingerprints and available correlation metadata. Repeated events are deduplicated independently of recurring patterns.
3. Analysis reads stored events, computes service-window features and clusters, then correlates evidence into incidents. The persisted result supports repeatable queries without recomputing features for every view.
4. Incident detail and report rendering use stored analysis outcomes and associated event evidence. Changing status updates lifecycle state.

## Persistence

| Data | Role |
| --- | --- |
| `imports` and `logs` | Dataset import statistics, normalized events and indexed service names |
| `analysis_runs` | Pipeline execution metadata and dependency information |
| `anomalies` and `clusters` | Statistical findings and recurring text patterns |
| `incidents` and `incident_events` | Investigation state, hypothesis and timeline payloads, and logged events supporting each group |
| Service summaries | Computed from stored events and investigation results |
| `settings` | Stored application configuration and optional service relationships |

Event time, service, severity and request or trace identifiers drive investigation queries. Primary and foreign keys give events, services, runs and incidents stable references. Database initialization creates the initial schema. A deployed version with existing user databases would need explicit migrations before model changes.

## Operating boundary

The app handles uploads and analysis on one instance. Workload limits, access controls, database backups, and private observability are deployment responsibilities for any larger installation. The [security policy](../SECURITY.md) describes the intended boundary.

