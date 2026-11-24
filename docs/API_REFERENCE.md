# API reference

The API prefix is `/api/v1`. In local development, the API base is `http://127.0.0.1:8000/api/v1`. In Docker, use `http://127.0.0.1:8080/api/v1`. Visit `/docs` or `/openapi.json` on the same origin for the generated Swagger UI and schema.

| Method | Path under the prefix | Purpose |
| --- | --- | --- |
| GET | `/health` | Service readiness |
| GET | `/analytics/summary` | Counts, recent incidents, log volume, severity distribution and service health |
| POST | `/logs/upload` | Import multipart form field `file` |
| POST | `/logs/demo` | Import the bundled synthetic log file |
| GET | `/logs` | List, page and filter events |
| GET | `/logs/{log_id}` | Fetch one stored event |
| GET | `/datasets` | List log imports and parsing statistics |
| GET | `/incidents` | List incidents |
| GET | `/incidents/{incident_id}` | Retrieve incident evidence, timeline and hypotheses |
| PATCH | `/incidents/{incident_id}/status` | Update lifecycle status |
| POST | `/analysis/run` | Run local analysis over stored events |
| GET | `/analysis/runs` | Inspect analysis runs |
| GET | `/anomalies` | List time-window anomaly results |
| GET | `/clusters` | List recurring log patterns |
| GET | `/services` | List services and their health signals |
| GET | `/services/dependencies` | Inspect configured and inferred relationships |
| GET | `/services/{service_id}` | Read one service's details |
| GET | `/settings` | Read persisted analysis settings |
| PUT | `/settings` | Update analysis parameters, dependencies and hypothesis weights |
| GET | `/reports/{incident_id}/markdown` | Export a human-readable incident report |
| GET | `/reports/{incident_id}/json` | Export structured incident evidence |

`limit` controls page size and `offset` selects the first result. Logs, incidents, anomalies and clusters return `items`, `total`, `limit`, and `offset`. Analysis runs and dataset imports accept the same paging parameters and return arrays. Analysis results for anomalies, clusters and dependencies reflect the latest run. Timestamps are UTC and serialized as ISO 8601 strings.

| Resource | Filters |
| --- | --- |
| Logs | `q` for message or service text, `service`, `severity`, `trace_id`, `request_id`, `start`, `end`, and `sort` (`asc` or `desc`) |
| Incidents | `service`, `severity`, `status`, `start`, and `end` |
| Anomalies | `service` and `anomalous` |

Upload errors include HTTP 400 for an empty file, HTTP 413 when a file exceeds the size limit, and HTTP 415 for an unsupported extension or binary input. HTTP 404 identifies an unknown record. HTTP 409 indicates another analysis is in progress. HTTP 422 identifies request validation errors. A status update may include `notes` to replace the incident notes.

Read settings with `GET /settings`, modify the returned object, and send it to `PUT /settings`. Defaults include a five-minute window, sensitivity of 0.08, a 12-minute correlation gap, and a threshold of four errors. `minimum_training_windows` defaults to 12, `isolation_estimators` to 100, and `cluster_similarity` to 0.26. Configured dependencies use `source` for the caller and `target` for the dependency. `root_cause_weights` overrides named weights from the [ranking methodology](ROOT_CAUSE_METHODOLOGY.md). A subsequent analysis run uses the updated settings.

## Examples

These shell commands assume local development. On Windows, use `curl.exe` if the shell maps `curl` to another command.

```bash
curl http://127.0.0.1:8000/api/v1/health
curl -X POST http://127.0.0.1:8000/api/v1/logs/demo
curl -X POST http://127.0.0.1:8000/api/v1/analysis/run
curl 'http://127.0.0.1:8000/api/v1/logs?severity=ERROR&limit=10&offset=0'
curl http://127.0.0.1:8000/api/v1/incidents
```

Upload your own file by substituting its path in the multipart request.

```bash
curl -F 'file=@your-logs.jsonl' http://127.0.0.1:8000/api/v1/logs/upload
```

Substitute a returned incident ID to update status and write both report formats.

```bash
INCIDENT_ID='replace-with-an-id'
curl -X PATCH -H 'Content-Type: application/json' \
  -d '{"status":"investigating"}' \
  "http://127.0.0.1:8000/api/v1/incidents/${INCIDENT_ID}/status"
curl -o report.md "http://127.0.0.1:8000/api/v1/reports/${INCIDENT_ID}/markdown"
curl -o report.json "http://127.0.0.1:8000/api/v1/reports/${INCIDENT_ID}/json"
```

Incident statuses are `open`, `investigating`, `resolved`, and `closed`. Input validation failures and rejected requests include a detail message or structured field error. A successful upload can also contain rejected records and duplicate counts, which describe the contents of the file.

