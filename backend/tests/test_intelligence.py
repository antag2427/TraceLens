from datetime import datetime, timedelta, timezone

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def log(identifier, minute, service, severity, message, trace=None):
    return {
        "id": identifier,
        "timestamp": (BASE + timedelta(minutes=minute)).isoformat(),
        "service": service,
        "severity": severity,
        "message": message,
        "normalized_message": message.lower(),
        "fingerprint": message.lower(),
        "trace_id": trace,
        "request_id": None,
        "host": None,
    }


def test_isolation_forest_flags_spike_and_inactivity():
    from app.ml import detect_anomalies

    events = [log(i, i * 5, "api", "INFO", "Request completed") for i in range(30) if i != 21]
    events += [log(30 + i, 125, "api", "ERROR", "Request timed out") for i in range(12)]
    windows = detect_anomalies(events, {})
    assert len(windows) == 30
    assert windows[25]["method"] == "isolation_forest+statistical"
    assert windows[25]["anomalous"]
    assert windows[21]["anomalous"]
    assert windows[21]["features"]["event_count"] == 0
    assert not windows[24]["anomalous"]


def test_small_sample_uses_statistical_fallback():
    from app.ml import detect_anomalies

    windows = detect_anomalies([log(1, 0, "db", "CRITICAL", "Database connection failed")], {})
    assert windows[0]["method"] == "statistical"
    assert windows[0]["anomalous"]


def test_related_text_clusters_and_handles_identical_messages():
    from app.ml import cluster_errors

    events = [
        log(1, 0, "db", "ERROR", "Database connection timeout"),
        log(2, 0, "db", "ERROR", "Database connection refused"),
        log(3, 1, "db", "ERROR", "Database query timeout"),
        log(4, 1, "auth", "ERROR", "Invalid authentication token"),
    ]
    clusters = cluster_errors(events, {})
    db = next(cluster for cluster in clusters if 1 in cluster["event_ids"])
    assert set(db["event_ids"]) == {1, 2, 3}
    assert "database" in db["keywords"]
    identical = cluster_errors(events[:1] + [log(5, 2, "db", "WARN", events[0]["message"])], {})
    assert len(identical) == 1
    assert identical[0]["severity_distribution"] == {"ERROR": 1, "WARN": 1}


def test_correlated_failures_rank_precursor_above_frequent_symptoms():
    from app.incidents import dependencies, detect_incidents

    events = [log(1, 0, "db", "CRITICAL", "Connection pool exhausted", "r1")]
    events += [log(i, i, "payment", "ERROR", "Payment request timed out", "r1") for i in range(2, 9)]
    events += [log(9, 9, "payment", "INFO", "Connection recovered", "r1")]
    events += [log(10, 4, "email", "ERROR", "SMTP authentication failed")]
    settings = {"dependencies": [{"source": "payment", "target": "db"}]}
    edges = dependencies(events, settings)
    incidents = detect_incidents(events, [], [], edges, settings)
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["services"] == ["db", "payment"]
    assert incident["hypotheses"][0]["service"] == "db"
    assert incident["hypotheses"][0]["confidence"] > incident["hypotheses"][1]["confidence"]
    assert incident["hypotheses"][0]["supporting_evidence"]
    assert incident["timeline"][-1]["kind"] == "recovery"
    assert incident["timeline"][-1]["event_id"] == 9


def test_dependency_inference_uses_shared_identifiers():
    from app.incidents import dependencies

    events = [
        log(1, 0, "db", "ERROR", "Connection failed", "r1"),
        log(2, 1, "api", "ERROR", "Request failed", "r1"),
        log(3, 8, "email", "INFO", "Message sent"),
    ]
    links = dependencies(events, {})
    assert [(link["source"], link["target"], link["kind"]) for link in links] == [
        ("api", "db", "inferred"),
    ]


def test_template_placeholders_do_not_create_error_themes():
    from app.ml import cluster_errors

    events = [
        log(1, 0, "api", "ERROR", "timeout <num>"),
        log(2, 1, "db", "ERROR", "deadlock <num>"),
    ]
    clusters = cluster_errors(events, {"cluster_similarity": 0.25})
    assert {tuple(cluster["event_ids"]) for cluster in clusters} == {(1,), (2,)}
    assert all("num" not in cluster["keywords"] for cluster in clusters)


def test_statistical_anomaly_alone_does_not_create_incident():
    from app.incidents import detect_incidents
    from app.ml import detect_anomalies

    events = [log(index, step * 5, "api", "INFO", "Regular request")
              for index, step in enumerate(range(24)) if step != 18]
    windows = detect_anomalies(events, {})
    assert any(window["anomalous"] for window in windows)
    assert detect_incidents(events, windows, [], [], {}) == []
