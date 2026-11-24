from fastapi.testclient import TestClient

from app.main import create_app


def test_demo_full_investigation_and_persistence(tmp_path):
    path = tmp_path / "test.sqlite3"
    with TestClient(create_app(path)) as client:
        prefix = "/api/v1"
        assert client.get(prefix + "/health").json()["status"] == "ok"
        upload = client.post(prefix + "/logs/upload", files={
            "file": ("sample.jsonl", b'{"timestamp":"2025-01-02","message":"ready"}\nbroken\n')
        })
        assert upload.status_code == 200, upload.text
        assert upload.json()["parsed"] == upload.json()["rejected"] == 1
        demo = client.post(prefix + "/logs/demo").json()
        assert demo["parsed"] >= 3000
        assert client.post(prefix + "/logs/demo").json()["duplicates"] == demo["parsed"]
        run = client.post(prefix + "/analysis/run").json()
        assert run["anomaly_count"] and run["cluster_count"]
        summary = client.get(prefix + "/analytics/summary").json()
        assert summary["total_events"] == demo["parsed"] + 1
        assert sum(bucket["errors"] for bucket in summary["volume"]) == sum(
            summary["severity_distribution"][level] for level in ("ERROR", "CRITICAL")
        )
        items = client.get(prefix + "/incidents").json()["items"]
        incident = next(item for item in items if len(item["services"]) >= 4)
        url = prefix + "/incidents/" + incident["id"]
        detail = client.get(url).json()
        assert detail["hypotheses"][0]["service"] == "database"
        assert any(item["id"] == incident["id"] for item in client.get(
            prefix + "/incidents", params={"service": "database", "severity": "critical"}
        ).json()["items"])
        related = client.get(prefix + "/logs", params={
            "service": "database", "trace_id": "cascade-000", "severity": "CRITICAL",
            "start": "2025-03-18T10:30:00Z", "end": "2025-03-18T10:31:00Z",
        }).json()
        assert related["total"] == 1 and related["items"][0]["incident_id"] == incident["id"]
        assert client.get(prefix + "/services/dependencies").json()
        assert client.get(prefix + "/anomalies", params={"anomalous": True}).json()["total"]
        times = [entry["timestamp"] for entry in detail["timeline"]]
        assert times == sorted(times)
        assert client.patch(url + "/status", json={"status": "investigating", "notes": "Inspect pool"}).status_code == 200
        report = prefix + "/reports/" + incident["id"]
        assert "Inspect pool" in client.get(report + "/markdown").text
        assert client.get(report + "/json").json()["hypotheses"][0]["supporting_evidence"]
        assert client.post(prefix + "/analysis/run").json()["incident_count"] == run["incident_count"]
    with TestClient(create_app(path)) as client:
        assert client.get(url).json()["status"] == "investigating"


def test_upload_rejects_oversize_and_unsupported_input(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACELENS_MAX_UPLOAD_BYTES", "32")
    with TestClient(create_app(tmp_path / "upload.sqlite3")) as client:
        endpoint = "/api/v1/logs/upload"
        assert client.post(endpoint, files={"file": ("a.log", b"x" * 33)}).status_code == 413
        assert client.post(endpoint, files={"file": ("a.exe", b"invalid")}).status_code == 415
        assert client.post(endpoint, files={"file": ("a.log", b"x" * 1_100_000)}).status_code == 413
        assert client.get("/api/v1/datasets").json() == []
