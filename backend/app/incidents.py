"""Correlate observed failures and rank explainable root-cause hypotheses."""

import re
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import timedelta
from hashlib import sha256
from itertools import combinations

from .features import ERROR_LEVELS, SIGNAL_LEVELS, timestamp

WARNING_LEVELS = SIGNAL_LEVELS - ERROR_LEVELS
CRITICAL_LEVELS = {"CRITICAL", "FATAL"}
RECOVERY = re.compile(r"\b(?:recover(?:ed|y)|restored|back online|healthy again|reconnected)\b", re.I)
NEGATED_RECOVERY = re.compile(r"\b(?:not|un|failed|unable|pending)\b.{0,45}\b(?:recover|restor|reconnect)", re.I)
ROOT_CAUSE_WEIGHTS = {
    "precedence": 0.22,
    "anomaly_onset": 0.12,
    "severity": 0.17,
    "dependencies": 0.18,
    "correlation": 0.13,
    "frequency": 0.08,
    "impact": 0.06,
    "propagation": 0.04,
}


def _identifiers(event: dict) -> tuple[tuple[str, str], ...]:
    return tuple((key, event[key]) for key in ("trace_id", "request_id") if event.get(key))


def _sort_key(event: dict) -> tuple:
    return timestamp(event["timestamp"]), event["id"]


def dependencies(events: list[dict], settings: dict) -> list[dict]:
    configured = {
        (link["source"], link["target"]): {
            "source": link["source"], "target": link["target"], "kind": "configured",
            "evidence": "Dependency declared in analysis settings.",
        }
        for link in settings.get("dependencies", [])
        if link["source"] != link["target"]
    }
    configured_pairs = {frozenset(pair) for pair in configured}
    by_identifier = defaultdict(dict)
    gap = timedelta(minutes=int(settings.get("incident_gap_minutes", 12)))
    ordered = sorted(events, key=_sort_key)
    for event in ordered:
        for identity in _identifiers(event):
            by_identifier[identity].setdefault(event["service"], timestamp(event["timestamp"]))

    shared = defaultdict(Counter)
    for (kind, _), services in by_identifier.items():
        for (first, first_at), (second, second_at) in combinations(services.items(), 2):
            if second_at - first_at <= gap:
                shared[tuple(sorted((first, second)))][kind, first, second] += 1

    # Consecutive short UTC bins provide weaker evidence when no shared
    # identifier exists. Require three independent co-occurrence bins.
    bins = defaultdict(dict)
    for event in ordered:
        if event["severity"] in ERROR_LEVELS:
            at = timestamp(event["timestamp"])
            bins[int(at.timestamp() // gap.total_seconds())].setdefault(event["service"], at)
    coincident = defaultdict(Counter)
    for services in bins.values():
        for first, second in combinations(services, 2):
            coincident[tuple(sorted((first, second)))][first, second] += 1

    inferred = {}
    for pair in sorted(shared.keys() | coincident.keys()):
        if frozenset(pair) in configured_pairs:
            continue
        if shared[pair]:
            votes = Counter()
            for (_, first, second), count in shared[pair].items():
                votes[first, second] += count
            (first, second), _ = votes.most_common(1)[0]
            traces = sum(count for (kind, _, _), count in shared[pair].items() if kind == "trace_id")
            requests = sum(count for (kind, _, _), count in shared[pair].items() if kind == "request_id")
            evidence = f"Shared {traces} trace and {requests} request identifiers. Edge direction follows observed order."
        elif sum(coincident[pair].values()) >= 3:
            (first, second), _ = coincident[pair].most_common(1)[0]
            evidence = f"Failures co-occurred in {sum(coincident[pair].values())} time windows. Direction is provisional."
        else:
            continue
        inferred[second, first] = {
            "source": second, "target": first, "kind": "inferred", "evidence": evidence,
        }
    return list(configured.values()) + list(inferred.values())


def _correlate(failures: list[dict], clusters: list[dict], edges: list[dict], gap: timedelta):
    cluster_ids = {
        event_id: cluster["id"]
        for cluster in clusters
        for event_id in cluster["event_ids"]
        if cluster["count"] >= 2
    }
    neighbors = defaultdict(set)
    for edge in edges:
        if edge["kind"] == "configured":
            neighbors[edge["source"]].add(edge["target"])
            neighbors[edge["target"]].add(edge["source"])

    parents = list(range(len(failures)))

    def component(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    recent = {}
    for index, event in enumerate(failures):
        service = event["service"]
        at = timestamp(event["timestamp"])
        keys = [("service", service), *(("id", key) for key in _identifiers(event))]
        if event["id"] in cluster_ids:
            keys.append(("cluster", cluster_ids[event["id"]]))
        for key in [*keys, *(("service", neighbor) for neighbor in neighbors[service])]:
            if key in recent:
                previous, previous_at = recent[key]
                if at - previous_at <= gap:
                    older, newer = sorted((component(index), component(previous)))
                    parents[newer] = older
        recent.update({key: (index, at) for key in keys})

    groups = defaultdict(list)
    for index, event in enumerate(failures):
        groups[component(index)].append(event)
    return groups.values()


def _relevant_anomalies(anomalies: list[dict], start, end, services: set[str]) -> list[dict]:
    return [
        item for item in anomalies
        if item["service"] in services
        and timestamp(item["timestamp"]) <= end
        and timestamp(item["end"]) > start
    ]


def _rank(failures: list[dict], anomalies: list[dict], edges: list[dict], settings: dict) -> list[dict]:
    first_at = timestamp(failures[0]["timestamp"])
    last_at = timestamp(failures[-1]["timestamp"])
    duration = max(1.0, (last_at - first_at).total_seconds())
    groups = defaultdict(list)
    first_by_service = {}
    ids_by_service = defaultdict(set)
    for event in failures:
        service = event["service"]
        groups[service, event["fingerprint"]].append(event)
        first_by_service.setdefault(service, timestamp(event["timestamp"]))
        ids_by_service[service].update(_identifiers(event))

    anomaly_onsets = {}
    for anomaly in sorted(anomalies, key=lambda item: timestamp(item["timestamp"])):
        anomaly_onsets.setdefault(anomaly["service"], timestamp(anomaly["timestamp"]))
    weights = {
        name: max(0.0, float(settings.get("root_cause_weights", {}).get(name, weight)))
        for name, weight in ROOT_CAUSE_WEIGHTS.items()
    }
    total_weight = sum(weights.values()) or 1.0
    max_occurrences = max(map(len, groups.values()))
    hypotheses = []
    for (service, _), matches in groups.items():
        first = matches[0]
        at = timestamp(first["timestamp"])
        delay = (at - first_at).total_seconds()
        later = {item for item, onset in first_by_service.items() if onset > at and item != service}
        earlier = {item for item, onset in first_by_service.items() if onset < at and item != service}
        identifiers = {identity for event in matches for identity in _identifiers(event)}
        linked = {
            item for item, identities in ids_by_service.items()
            if item != service and identifiers.intersection(identities)
        }
        downstream = {
            edge["source"]: (1.0 if edge["kind"] == "configured" else 0.45)
            for edge in edges if edge["target"] == service and edge["source"] in later
        }
        onset = anomaly_onsets.get(service)
        earliest_onset = min(anomaly_onsets.values(), default=first_at)
        onset_score = max(0.0, 1 - (onset - earliest_onset).total_seconds() / duration) if onset else 0.0
        maximum_downstream = max(len(first_by_service) - 1, 1)
        critical = any(event["severity"] in CRITICAL_LEVELS for event in matches)
        signals = {
            "precedence": max(0.0, 1 - delay / duration),
            "anomaly_onset": onset_score,
            "severity": 1.0 if critical else 0.6,
            "dependencies": sum(downstream.values()) / maximum_downstream,
            "correlation": len(linked) / maximum_downstream,
            "frequency": len(matches) / max_occurrences,
            "impact": len(later) / maximum_downstream,
            "propagation": len(later.intersection(linked)) / maximum_downstream,
        }
        temporal = (
            "This pattern appeared at the first observed failure timestamp."
            if not delay else f"This pattern first appeared {delay:g} seconds after the first observed failure."
        )
        supporting = [temporal, f"{len(matches)} occurrences of this pattern were observed."]
        contradicting = []
        if critical:
            supporting.append("At least one event with this pattern had critical severity.")
        if onset:
            supporting.append(f"The first nearby anomalous window for this service began at {onset.isoformat()}.")
        if linked:
            supporting.append(f"Trace or request identifiers overlap with {', '.join(sorted(linked))}.")
        if later:
            supporting.append(f"Failures appeared later in {', '.join(sorted(later))}.")
        if downstream:
            supporting.append(f"Later failures appeared in dependent services {', '.join(sorted(downstream))}, based on available dependency evidence.")
        if earlier:
            contradicting.append(f"Earlier failures were observed in {', '.join(sorted(earlier))}.")
        if not linked and len(first_by_service) > 1:
            contradicting.append("No shared trace or request identifier links this pattern to other affected services.")
        contributions = sorted(
            ((weights[key] * value, key) for key, value in signals.items() if weights[key] * value > 0),
            reverse=True,
        )
        leading = ", ".join(name.replace("_", " ") for _, name in contributions[:3]) or "none"
        hypotheses.append({
            "service": service,
            "pattern": first["normalized_message"] or first["message"],
            "confidence": round(sum(value for value, _ in contributions) / total_weight, 3),
            "supporting_evidence": supporting,
            "contradicting_evidence": contradicting,
            "temporal_relationship": temporal,
            "explanation": f"Largest ranking contributions were {leading}. Confidence is a relative evidence score and causal attribution remains uncertain.",
        })
    ranked = sorted(hypotheses, key=lambda item: (-item["confidence"], item["service"], item["pattern"]))[:5]
    if len(ranked) > 1:
        lead, runner_up = ranked[:2]
        lead["explanation"] += (
            f" The next hypothesis ({runner_up['service']}) scored {runner_up['confidence']:.3f} "
            f"versus {lead['confidence']:.3f} for this hypothesis."
        )
    return ranked


def _timeline(events: list[dict], anomalies: list[dict]) -> list[dict]:
    entries = []
    first_failure = next((event for event in events if event["severity"] in ERROR_LEVELS), None)
    first_warning, seen = True, set()
    for event in events:
        pattern = event["service"], event["fingerprint"]
        kind = "event"
        if event["severity"] in WARNING_LEVELS:
            kind, first_warning = ("first_warning" if first_warning else "warning"), False
        if event["severity"] in ERROR_LEVELS:
            kind = "first_error" if event is first_failure else "service_failure"
            if pattern in seen:
                kind = "repeated_failure"
            elif (
                first_failure and event["service"] != first_failure["service"]
                and set(_identifiers(event)).intersection(_identifiers(first_failure))
            ):
                kind = "correlated_failure"
            seen.add(pattern)
        if event["severity"] not in ERROR_LEVELS and RECOVERY.search(event["message"]) and not NEGATED_RECOVERY.search(event["message"]):
            kind = "recovery"
        entries.append({
            "timestamp": event["timestamp"], "service": event["service"], "severity": event["severity"],
            "message": event["message"], "event_id": event["id"], "kind": kind,
            "trace_id": event.get("trace_id"), "request_id": event.get("request_id"),
        })
    entries.extend({
        "timestamp": item["timestamp"], "service": item["service"], "severity": item["severity"],
        "message": item["explanation"], "kind": "anomaly",
    } for item in anomalies)
    return sorted(entries, key=lambda item: timestamp(item["timestamp"]))


def detect_incidents(events: list[dict], anomalies: list[dict], clusters: list[dict], edges: list[dict], settings: dict) -> list[dict]:
    gap = timedelta(minutes=int(settings.get("incident_gap_minutes", 12)))
    minimum = int(settings.get("min_errors", 4))
    ordered = sorted(events, key=_sort_key)
    failures = [event for event in ordered if event["severity"] in ERROR_LEVELS]
    signals = [event for event in ordered if event["severity"] not in ERROR_LEVELS]
    signal_times = [timestamp(event["timestamp"]) for event in signals]
    flagged = [item for item in anomalies if item["anomalous"]]
    incidents = []
    for group in _correlate(failures, clusters, edges, gap):
        first, last = group[0], group[-1]
        start, end = timestamp(first["timestamp"]), timestamp(last["timestamp"])
        services = {event["service"] for event in group}
        nearby = _relevant_anomalies(flagged, start - gap, end, services)
        critical = any(event["severity"] in CRITICAL_LEVELS for event in group)
        if not (critical or len(group) >= minimum or (len(group) >= 2 and nearby)):
            continue

        identifiers = {identity for event in group for identity in _identifiers(event)}
        related = list(group)
        left = bisect_left(signal_times, start - gap)
        right = bisect_left(signal_times, end + gap)
        for event in signals[left:right]:
            if event["service"] not in services:
                continue
            at = timestamp(event["timestamp"])
            shared = identifiers.intersection(_identifiers(event))
            warning = event["severity"] in WARNING_LEVELS and at <= end
            recovery = at >= start and RECOVERY.search(event["message"]) and not NEGATED_RECOVERY.search(event["message"])
            if shared or warning or recovery:
                related.append(event)
        related.sort(key=_sort_key)
        event_ids = [event["id"] for event in related]
        local_ids = set(event_ids)
        related_clusters = [cluster for cluster in clusters if local_ids.intersection(cluster["event_ids"])]
        related_edges = [edge for edge in edges if edge["source"] in services and edge["target"] in services]
        severity = "critical" if critical else "high" if len(group) >= minimum * 2 else "medium" if len(group) >= minimum else "low"
        title = (first["normalized_message"] or first["message"]).strip()[:100]
        title = title[0].upper() + title[1:] if title else "Service failure"
        key = f"{first['service']}\0{first['timestamp']}\0{first['fingerprint']}\0{first['id']}"
        incidents.append({
            "id": f"incident-{sha256(key.encode()).hexdigest()[:16]}",
            "title": title,
            "description": f"{len(group)} errors observed across {len(services)} services with correlated activity.",
            "severity": severity,
            "first_seen": first["timestamp"],
            "last_seen": related[-1]["timestamp"],
            "services": sorted(services),
            "event_count": len(event_ids),
            "event_ids": event_ids,
            "anomalies": nearby,
            "clusters": related_clusters,
            "timeline": _timeline(related, nearby),
            "hypotheses": _rank(group, nearby, related_edges, settings),
            "dependencies": related_edges,
        })
    return sorted(incidents, key=lambda item: timestamp(item["first_seen"]), reverse=True)
