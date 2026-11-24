# Project guide

## Investigate the demo

1. Start the containers or local development processes using the [README](../README.md).
2. Load the committed demo file and start an analysis. Open the overview to establish the total traffic, severities and affected services.
3. Open the explorer and filter for the database service and error severity. Select an entry and note its UTC time and trace or request ID.
4. Inspect unusual service windows and cluster representative messages. Compare a repeated database error with the later payment and checkout failures.
5. Open the incident and review the sequence, strongest hypothesis and corroborating evidence. Consult the dependency view to see how relationship provenance is represented.
6. Change status to Investigating. Save the JSON report for structured evidence and Markdown for a human-readable handoff.

## Try your own input

Upload one small file under `data/samples/` to learn how formats map to normalized fields. Add an invalid timestamp to a copy and inspect the skipped-record feedback. Upload the same valid file twice and compare imported and duplicate counts. Keep private logs out of the versioned tree.

## Read the implementation

Start with `backend/app/main.py`, then work through `api.py`, `schemas.py`, `db.py`, `ingestion.py`, `analysis.py`, `features.py`, `ml.py`, `incidents.py`, and `frontend/src/main.tsx`. The [learning guide](LEARNING_GUIDE.md) links these files to experiments. The [API reference](API_REFERENCE.md) documents how the frontend and scripts reach the backend.

