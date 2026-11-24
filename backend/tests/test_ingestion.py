import io

import pytest

from app.ingestion import records, normalize


@pytest.mark.parametrize(("name", "content"), [
    ("x.json", b'[{"timestamp":"2025-01-01T05:30:00+05:30","service":"db","level":"ERR","message":"Timeout 1032"}]'),
    ("x.jsonl", b'{"timestamp":"2025-01-01T05:30:00+05:30","service":"db","level":"ERR","message":"Timeout 1032"}\n'),
    ("x.csv", b'timestamp,service,level,message\n2025-01-01T05:30:00+05:30,db,ERR,Timeout 1032\n'),
    ("x.log", b'2025-01-01T05:30:00+05:30 ERR db Timeout 1032\n'),
])
def test_formats_and_utc(name, content):
    index, row = next(records(io.BytesIO(content), name))
    assert index == 1
    event = normalize(row, name)
    assert (event["timestamp"], event["severity"], event["service"]) == (
        "2025-01-01T00:00:00.000000Z", "ERROR", "db"
    )
    assert event["normalized_message"] == "timeout <num>"


def test_malformed_rows_are_visible_and_iteration_continues():
    entries = list(records(io.BytesIO(b'invalid\n{"message":"ok"}\n'), "x.jsonl"))
    assert isinstance(entries[0][1], ValueError)
    with pytest.raises(ValueError, match="timestamp"):
        normalize(entries[1][1], "x.jsonl")


def test_source_independent_dedup_and_redaction():
    row = {"timestamp": "2025-01-01", "message": "password=private-value", "password": "private-value"}
    first = normalize(row, "a.csv")
    second = normalize(row, "b.json")
    assert first["dedup_key"] == second["dedup_key"]
    assert "private-value" not in str(first)
    assert first["service"] == "unknown"
