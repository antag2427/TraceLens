"""Bounded ingestion and source-independent event identity."""

import csv
import hashlib
import io
import json
import re
import time
from datetime import UTC, datetime
from pathlib import PurePosixPath

import ijson
from sqlalchemy.dialects.sqlite import insert

from .db import Import, Log

EXTENSIONS = {".json", ".jsonl", ".ndjson", ".csv", ".log", ".txt"}
LEVELS = {"ERR": "ERROR", "WARN": "WARNING", "FATAL": "CRITICAL", "TRACE": "DEBUG"}
SEVERITIES = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
SECRET_KEY = re.compile(r"password|passwd|secret|token|authorization|api[-_ ]?key", re.I)
SECRET_VALUE = re.compile(
    r"""(?i)\b(password|passwd|secret|(?:access[_-]?)?token|api[-_ ]?key|authorization)(["']?\s*[:=]\s*)(?:bearer\s+)?(?:"[^"]*"|'[^']*'|[^\s,;&]+)"""
)
PLAIN = re.compile(
    r"^\[?(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]?"
    r"\s+\[?(?P<severity>[A-Z]+)\]?\s+\[?(?P<service>[\w./-]+)\]?(?:\s*[-:]\s*|\s+)(?P<message>.+)$",
    re.I,
)
VARIABLES = [
    (r"\b\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:[.,]\d+)?(?:Z|[+-]\d\d:?\d\d)?", "<time>"),
    (r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", "<uuid>"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<ip>"),
    (r"\b(?:trace|request)[_-]?(?:id)?[=:]\s*[\w.-]+", "<correlation>"),
    (r"\b\d+(?:\.\d+)?\b", "<num>"),
]


def utc(value):
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
            instant = datetime.fromtimestamp(number / 1000 if abs(number) >= 1e12 else number, UTC)
        else:
            instant = datetime.fromisoformat(str(value).replace(",", ".").replace("Z", "+00:00"))
        return instant.replace(tzinfo=instant.tzinfo or UTC).astimezone(UTC).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        raise ValueError("Missing or invalid timestamp") from exc


def now():
    return utc(datetime.now(UTC))


def safe_name(name):
    return PurePosixPath(name.replace("\\", "/")).name[:255]


def extension(name):
    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in EXTENSIONS:
        raise ValueError("Supported extensions are JSON, JSONL, NDJSON, CSV, LOG and TXT")
    return suffix


def records(stream, name):
    """Yield (record number, object or validation error) from a binary file."""
    suffix = extension(name)
    if suffix == ".json":
        lead = stream.read(4096)
        stream.seek(0)
        if lead.startswith(b"\xef\xbb\xbf"):
            stream.seek(3)
            lead = lead[3:]
        if lead.lstrip().startswith(b"{"):
            try:
                yield 1, json.load(stream, parse_constant=lambda _: None)
            except (ValueError, UnicodeError, RecursionError):
                yield 1, ValueError("Invalid JSON object")
            return
        if not lead.lstrip().startswith(b"["):
            yield 1, ValueError("Expected a JSON object or array")
            return
        index = 0
        try:
            for index, item in enumerate(ijson.items(stream, "item", use_float=True), 1):
                yield index, item
        except (ijson.JSONError, UnicodeError, ValueError, OverflowError):
            yield index + 1, ValueError("Invalid JSON array")
        return
    with io.TextIOWrapper(stream, encoding="utf-8-sig", errors="surrogateescape", newline="") as source:
        if suffix == ".csv":
            reader = csv.DictReader(source, strict=True)
            try:
                if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                    raise csv.Error
                for index, row in enumerate(reader, 1):
                    if None in row:
                        yield index, ValueError("Too many CSV fields")
                    else:
                        yield index, row
            except csv.Error:
                yield max(1, reader.line_num - 1), ValueError("Invalid CSV structure")
            return
        for index, line in enumerate(source, 1):
            if not line.strip():
                continue
            if suffix in {".jsonl", ".ndjson"}:
                try:
                    yield index, json.loads(line, parse_constant=lambda _: None)
                except (ValueError, RecursionError):
                    yield index, ValueError("Invalid JSON line")
            else:
                match = PLAIN.fullmatch(line.strip())
                if not match:
                    yield index, ValueError("Expected timestamp, severity, service and message")
                    continue
                row = match.groupdict()
                for key in ("trace_id", "request_id", "host"):
                    field = re.search(rf"\b{key}[=:]([\w.:-]+)", row["message"])
                    if field:
                        row[key] = field[1]
                yield index, row


def redact(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if SECRET_KEY.search(key) else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SECRET_VALUE.sub(r"\1\2[REDACTED]", value)
    return value


def digest(*values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=True, sort_keys=True).encode()).hexdigest()


def normalize(row, name):
    if isinstance(row, ValueError):
        raise row
    if not isinstance(row, dict):
        raise ValueError("Expected an object")
    try:
        json.dumps(row, ensure_ascii=False).encode("utf-8")
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Invalid text encoding or deeply nested data") from exc
    row = {key.strip().lower(): value for key, value in row.items()}
    used = set()

    def field(*keys, default=None):
        used.update(keys)
        return next((row[key] for key in keys if row.get(key) not in (None, "")), default)

    timestamp = utc(field("timestamp", "time", "ts", "@timestamp"))
    raw_message = field("message", "msg", "event")
    if not isinstance(raw_message, str) or not raw_message.strip():
        raise ValueError("Missing or invalid message")
    if "\x00" in raw_message or len(raw_message) > 65536:
        raise ValueError("Message contains a null byte or exceeds 65536 characters")
    message = redact(raw_message.strip())
    service = str(field("service", "service_name", "logger", default="unknown")).strip()[:150] or "unknown"
    level = str(field("severity", "level", "log_level", default="INFO")).strip().upper()
    severity = LEVELS.get(level, level)
    if severity not in SEVERITIES:
        raise ValueError("Unrecognized severity")
    trace_id = field("trace_id", "traceid", "trace")
    request_id = field("request_id", "requestid", "request")
    host = field("host", "hostname")
    trace_id, request_id, host = (str(value)[:255] if value is not None else None
                                  for value in (trace_id, request_id, host))
    normalized = " ".join(message.lower().split())
    for pattern, replacement in VARIABLES:
        normalized = re.sub(pattern, replacement, normalized)
    attributes = redact({key: value for key, value in row.items() if key not in used})
    return dict(timestamp=timestamp, message=message, service=service, severity=severity,
                normalized_message=normalized, trace_id=trace_id, request_id=request_id,
                host=host, source_file=name, attributes=attributes,
                fingerprint=digest(normalized),
                dedup_key=digest(timestamp, service, severity, message, trace_id, request_id, host, attributes))


def ingest(session, stream, name):
    name = safe_name(name)
    extension(name)
    started = time.perf_counter()
    upload = Import(source_file=name, created_at=now(), result={})
    session.add(upload)
    session.flush()
    result = dict(processed=0, parsed=0, rejected=0, duplicates=0, errors=[])
    services = set()
    batch = []

    def write_batch():
        if batch:
            statement = insert(Log.__table__).on_conflict_do_nothing(index_elements=["dedup_key"])
            added = session.execute(statement, batch).rowcount
            result["parsed"] += added
            result["duplicates"] += len(batch) - added
            batch.clear()

    for index, row in records(stream, name):
        result["processed"] += 1
        try:
            item = normalize(row, name)
        except ValueError as exc:
            result["rejected"] += 1
            if len(result["errors"]) < 50:
                result["errors"].append(dict(record=index, message=str(exc)))
            continue
        item["import_id"] = upload.id
        services.add(item["service"])
        batch.append(item)
        if len(batch) == 500:
            write_batch()
    write_batch()
    if not result["processed"]:
        result["processed"] = result["rejected"] = 1
        result["errors"].append(dict(record=1, message="No data records found"))
    result.update(services=sorted(services), duration_ms=round(1000 * (time.perf_counter() - started)))
    upload.result = result
    session.commit()
    return result
