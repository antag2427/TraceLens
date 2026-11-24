"""Serialize incident evidence for offline investigation."""

from datetime import datetime


def build_report(incident):
    elapsed = datetime.fromisoformat(incident["last_seen"]) - datetime.fromisoformat(incident["first_seen"])
    steps = [
        "Review the earliest warning and error against deployment and service health records.",
        "Use the shared trace or request IDs to inspect related service calls.",
        "Verify upstream and downstream dependencies against configuration or tracing data.",
        "Check recovery records and record the evidence that confirms or rules out each hypothesis.",
    ]
    return {**incident, "duration_seconds": int(elapsed.total_seconds()),
            "recommended_steps": steps,
            "uncertainty": "Hypothesis scores rank evidence. They do not measure causal probability."}


def markdown(report):
    lines = [
        f'# {report["title"]}', "", report["description"], "",
        f'- Severity — {report["severity"]}',
        f'- Status — {report["status"]}',
        f'- Observed from {report["first_seen"]} through {report["last_seen"]}',
        f'- Duration — {report["duration_seconds"]} seconds',
        f'- Related events — {report["event_count"]}',
        f'- Services — {", ".join(report["services"])}', "",
        "## Statistical anomalies", "",
    ]
    lines.extend(f'- {a["timestamp"]} · {a["service"]} · {a["score"]:.3f} · {a["explanation"]}'
                 for a in report["anomalies"])
    lines.extend(["", "## Common error patterns", ""])
    lines.extend(f'- {c["title"]} ({c["count"]} records)' for c in report["clusters"])
    lines.extend(["", "## Observed timeline", ""])
    lines.extend(f'- {e["timestamp"]} · {e["service"]} · {e["severity"]} · {e["message"]}'
                 for e in report["timeline"])
    lines.extend(["", "## Root-cause hypotheses", "", report["uncertainty"]])
    for hypothesis in report["hypotheses"]:
        lines.extend(["", f'### {hypothesis["service"]} · {hypothesis["confidence"]:.0%}',
                      "", hypothesis["pattern"], "", hypothesis["temporal_relationship"], "",
                      hypothesis["explanation"]])
        lines.extend(f'- Supporting evidence — {item}' for item in hypothesis["supporting_evidence"])
        lines.extend(f'- Contradicting evidence — {item}' for item in hypothesis["contradicting_evidence"])
    lines.extend(["", "## Correlated or configured relationships", ""])
    lines.extend(f'- {e["source"]} → {e["target"]} ({e["kind"]}) · {e["evidence"]}' for e in report["dependencies"])
    lines.extend(["", "## Recommended investigation steps", ""])
    lines.extend(f'- {step}' for step in report["recommended_steps"])
    lines.extend(["", "## Resolution notes", "", report["notes"] or "No notes recorded.", ""])
    return "\n".join(lines)
