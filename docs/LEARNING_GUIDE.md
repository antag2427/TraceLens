# Learning guide

Use a temporary local database and the bundled demo. Work through these modules in order, or use the practical exercise to enter at the part you want to study.

## Module 1 — Overall architecture

TraceLens follows an upload, analyze, investigate cycle. Keeping ingestion, analysis, and rendering separate makes outputs reproducible and each layer easier to test. Read `backend/app/main.py`, `backend/app/analysis.py`, `frontend/src/main.tsx`, and `docker-compose.yml`. The React client calls FastAPI, which reads and writes SQLite. Before changing the architecture, identify which process owns each operation and whether its data belongs to an upload, analysis run, or incident. Exercise: load the demo while watching browser Network requests and follow one request into the backend.

## Module 2 — Python backend and FastAPI

FastAPI maps typed HTTP requests onto application functions. Read `backend/app/main.py`, `api.py`, and `schemas.py`. Pydantic validates inputs and shapes the HTTP contract. Handlers connect uploads and settings to application logic, then return stable response fields for the frontend. Know which checks belong at the API boundary and which apply in the analysis layer before modifying a route. Exercise: submit a malformed status update in Swagger UI and inspect its validation response.

## Module 3 — Database design and SQLAlchemy

SQLite retains data after restart. Read `backend/app/db.py` and the API tests. SQLAlchemy maps tables and relationships so a persisted incident can refer to its analysis and source events. Understand data identity, transaction scope, and relationships before changing any table. Exercise: load demo data into a temporary database, restart the backend with the same file path, and query the event count again.

## Module 4 — Data ingestion and log parsing

Read `backend/app/ingestion.py` and the ingestion tests. Parsers turn JSON, JSONL, CSV, and supported plain text into records with a common structure. The upload route receives the parser's totals and error details. Understand which formats can be read by row and how file versus record errors are represented. Exercise: upload a copy of one sample with a malformed entry and check whether valid neighbors are preserved.

## Module 5 — Data cleaning and normalization

Read `backend/app/ingestion.py` and inspect a response from the log detail endpoint. UTC timestamps support global ordering, severity normalization supports comparisons, and message templates reduce variation from IDs and other changing values. The normalized fields feed feature extraction, clustering, and search. Learn which normalization affects event deduplication and which affects grouping. Exercise: upload two otherwise similar timeout messages with different numeric IDs and compare the individual records and fingerprints.

## Module 6 — Feature engineering

Read `backend/app/features.py`. The NumPy-based anomaly detector uses service-window vectors containing event volume, critical/error/warning counts, error share, distinct errors, message length, timeout and database counts, changes in event volume, and rolling baselines. These vectors are the inputs to anomaly detection. Understand bucket boundaries and how missing activity is represented. Exercise: compare two window widths on the same log corpus and inspect the resulting feature values around onset.

## Module 7 — Isolation Forest

Read `backend/app/ml.py` and the intelligence tests. Isolation Forest chooses random feature splits; unusual rows generally take fewer splits to isolate. The model scores independently fitted service windows and supplements median-based statistical signals. Review contamination, the small-sample fallback, and the distinction between a score and a classification before changing thresholds. Exercise: run an analysis on a short service history and compare its detector method with the full demo.

## Module 8 — TF-IDF and text vectorization

Read `backend/app/ml.py`. TF-IDF converts normalized warning and error templates into sparse vectors whose term weights reflect each template and the corpus. Clustering uses those vectors, with the input template retaining a link to the source events. Learn how tokenization, stop words and corpus size affect weights. Exercise: add two related timeout messages and an unrelated authentication message to a small dataset, then compare their cluster keywords.

## Module 9 — Clustering algorithms

Read the clustering functions in `backend/app/ml.py`. Small corpora use connected components formed from cosine-similarity matches. Larger corpora use MiniBatchKMeans to assign patterns to centroids. The cluster summaries provide representative messages, frequency, services and time ranges to the UI and incident engine. Learn how transitive similarity can combine two patterns and how cluster size differs from distinct template count. Exercise: compare clustering before and after adding an intermediate pattern that shares useful terms with two existing groups.

## Module 10 — Incident detection

Read `backend/app/incidents.py`, `analysis.py`, and the intelligence tests. Incident correlation groups abnormal service windows and related errors using proximity, severity, frequency and log identifiers. The result contains a bounded investigation with related events and analysis evidence. Learn the grouping and deduplication rules before changing significance criteria. Exercise: rerun the same analysis and compare incident identities, counts and any edited statuses.

## Module 11 — Root cause analysis

Read `backend/app/incidents.py` and the [methodology](ROOT_CAUSE_METHODOLOGY.md). A weighted ranking combines evidence about onset, severity, shared identifiers, dependencies or propagation, and plausible alternate explanations. It serves the incident detail and reports. Know which signals express observations and which rely on inference. Exercise: compare the demo's leading two candidates and find one linked event that supports each rank.

## Module 12 — Timeline reconstruction

Read `backend/app/incidents.py`, `backend/app/reports.py`, and the incident views under `frontend/src/`. The timeline orders member events and anomaly findings in UTC for sequence reconstruction and comparison. It is used in the incident detail and export. Learn the difference between a source event timestamp and a derived anomaly window before adjusting chronology. Exercise: filter the incident timeline by service or severity and then compare the full JSON export.

## Module 13 — REST API integration

Read `backend/app/api.py`, `schemas.py`, and `frontend/src/api.ts`. The versioned JSON API exposes models, filtered collections, uploads and report endpoints. The client wraps browser fetch for JSON and uses multipart upload with progress reporting. Check request names, error shapes and pagination together before changing a shared field. Exercise: request a filtered log page directly in Swagger UI and issue the same search from the frontend.

## Module 14 — React frontend

Read `frontend/src/main.tsx`, `api.ts`, and `ui.tsx`. React renders navigation and views, Tailwind provides styling, Recharts displays analysis data, and Lucide supplies icons. The frontend obtains results through the API and refreshes data after operations such as uploads or status changes. Understand loading, failure, and empty states and use the typed response structures. Exercise: reduce viewport width and confirm that you can still navigate and filter the log explorer.

## Module 15 — Docker and deployment

Read `docker-compose.yml`, both Dockerfiles and `frontend/nginx.conf`. The Python container runs the API, the Nginx container serves compiled frontend files, and a named volume preserves SQLite. The internal network and reverse proxy allow same-origin requests. Know the distinction between published host ports and service-to-service addresses. Exercise: inspect `docker compose config`, run the stack, load demo data, and confirm it remains available after a container restart.

## Module 16 — Testing and CI/CD

Read `backend/tests/`, `frontend/package.json`, and `.github/workflows/ci.yml`. Pytest exercises ingestion, machine learning, correlation and routes with controlled fixtures. TypeScript, ESLint and the Vite build catch frontend contract, code and bundling issues. CI reproduces those checks on pushes and pull requests. Understand the fixture setup and check the smallest relevant behavior before changing an assertion. Exercise: run one backend test file, then the full suite and the three frontend checks.

