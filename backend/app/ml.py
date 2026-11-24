"""Local Isolation Forest, statistical outliers, and TF-IDF error themes."""

import re
from collections import Counter, defaultdict
from hashlib import sha256

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from threadpoolctl import threadpool_limits

from .features import FEATURE_DESCRIPTIONS, SIGNAL_LEVELS, service_windows, timestamp

DIRECT_FEATURES = tuple(FEATURE_DESCRIPTIONS)[:9]
PLACEHOLDER = re.compile(r"<(?:num|uuid|ip|time|correlation)>|\[redacted\]", re.I)


def _statistical_score(features: dict, baseline: list[dict]) -> tuple[float, list[str]]:
    if len(baseline) < 4:
        if features["critical_count"]:
            return 0.8, ["Critical activity observed with limited service history."]
        if features["error_count"] >= 3:
            return 0.65, ["Multiple errors observed in a window with limited service history."]
        return 0.0, []

    signals = []
    fields = ("event_count", "error_count", "warning_count", "critical_count", "timeout_count", "database_error_count", "unique_errors")
    for name in fields:
        samples = np.array([item[name] for item in baseline])
        # Include zeros for error/warning baselines, but avoid treating recovery
        # from a long idle period as anomalous solely because volume resumed.
        if name == "event_count":
            samples = samples[samples > 0]
        if len(samples) < 4:
            continue
        center = float(np.median(samples))
        deviation = float(np.median(np.abs(samples - center)))
        value = features[name]
        if name == "event_count" and value == 0:
            signals.append((3.5, f"Service inactivity observed versus a recent median of {center:g} events."))
            continue
        scale = max(1.0, 1.4826 * deviation, float(np.sqrt(center)) * 0.5)
        strength = (value - center) / scale
        if strength >= 2.5:
            signals.append((strength, f"{FEATURE_DESCRIPTIONS[name].capitalize()} increased to {value:g} from a recent median of {center:g}."))
    signals.sort(reverse=True)
    if not signals:
        return 0.0, []
    return min(0.98, 0.5 + 0.06 * signals[0][0]), [message for _, message in signals[:3]]


def detect_anomalies(events: list[dict], settings: dict) -> list[dict]:
    sensitivity = float(settings.get("sensitivity", 0.08))
    minimum = int(settings.get("minimum_training_windows", 12))
    estimators = int(settings.get("isolation_estimators", 100))
    results = []
    for service, windows in service_windows(events, int(settings.get("window_minutes", 5))).items():
        rows = [window["features"] for window in windows]
        matrix = pd.DataFrame.from_records(rows, columns=FEATURE_DESCRIPTIONS).to_numpy(dtype=float)
        decisions = np.zeros(len(rows))
        model_ready = len(rows) >= minimum and np.any(np.ptp(matrix, axis=0) > 0)
        if model_ready:
            model = IsolationForest(n_estimators=estimators, contamination=sensitivity, random_state=42)
            decisions = model.fit(matrix).decision_function(matrix)
        for i, (window, decision) in enumerate(zip(windows, decisions)):
            row = rows[i]
            baseline = rows[max(0, i - 24):i]
            robust, drivers = _statistical_score(row, baseline)
            # A window may be unusual only because its lagged context changed.
            # Require an unusual direct observation before using the model flag.
            context = baseline or rows
            direct_changes = []
            for name in DIRECT_FEATURES:
                median = float(np.median([prior[name] for prior in context]))
                if row[name] != median:
                    direct_changes.append((abs(float(row[name]) - median) / max(abs(median), 1), name, median))
            model_flag = bool(decision < -1e-9 and direct_changes)
            flag = model_flag or robust >= 0.6
            if not drivers and model_flag:
                strongest = sorted(direct_changes, reverse=True)[:2]
                drivers = [
                    f"{FEATURE_DESCRIPTIONS[name].capitalize()} was {row[name]:.2g} versus a baseline median of {median:.2g}."
                    for _, name, median in strongest
                ]
            severity = "normal"
            if flag:
                severity = "high" if row["critical_count"] or row["error_count"] >= 5 else "medium"
                if not row["critical_count"] and not row["error_count"] and not row["warning_count"]:
                    severity = "low"
            results.append({
                **window,
                "id": f"{service}@{window['timestamp']}",
                "service": service,
                "score": round(max(robust, float(np.clip(0.5 - decision, 0, 1)) if model_ready else 0), 4),
                "anomalous": flag,
                "severity": severity,
                "method": "isolation_forest+statistical" if model_ready else "statistical",
                "explanation": " ".join(drivers) if drivers else "No outlier signals exceeded the detection criteria.",
            })
    return sorted(results, key=lambda item: (item["timestamp"], item["service"]))


def _small_clusters(matrix, threshold: float) -> list[int]:
    # Connected components on cosine similarity. Sparse TF-IDF rows have unit norm.
    similarity = (matrix @ matrix.T).tocoo()
    parent = list(range(matrix.shape[0]))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left, right, score in zip(similarity.row, similarity.col, similarity.data):
        if left < right and score >= threshold:
            parent[root(right)] = root(left)
    return [root(index) for index in range(len(parent))]


def cluster_errors(events: list[dict], settings: dict) -> list[dict]:
    by_template = defaultdict(list)
    for event in events:
        if event["severity"] in SIGNAL_LEVELS:
            template = event["normalized_message"] or event["message"]
            by_template[template].append(event)
    templates = sorted(by_template)
    if not templates:
        return []

    vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[^\W\d_][^\W\d]+\b", stop_words="english")
    matrix = None
    try:
        matrix = vectorizer.fit_transform(PLACEHOLDER.sub(" ", template) for template in templates)
    except ValueError as error:
        if "empty vocabulary" not in str(error):
            raise

    if matrix is None:
        labels = range(len(templates))
    elif len(templates) <= 400:
        labels = _small_clusters(matrix, float(settings.get("cluster_similarity", 0.26)))
    else:
        count = min(40, max(2, round(np.sqrt(len(templates) / 2))))
        with threadpool_limits(limits=1):
            labels = MiniBatchKMeans(n_clusters=count, n_init=5, random_state=42).fit_predict(matrix)

    groups = defaultdict(list)
    for index, label in enumerate(labels):
        groups[label].append(index)

    clusters = []
    vocabulary = vectorizer.get_feature_names_out() if matrix is not None else []
    for indexes in groups.values():
        matching = sorted(
            (event for index in indexes for event in by_template[templates[index]]),
            key=lambda event: (timestamp(event["timestamp"]), event["id"]),
        )
        counts = Counter(event["message"] for event in matching)
        weights = np.asarray(matrix[indexes].mean(axis=0)).ravel() if matrix is not None else []
        keywords = [str(vocabulary[index]) for index in np.argsort(-weights)[:5] if weights[index] > 0] if len(weights) else []
        label = " / ".join(keywords[:3]) if keywords else matching[0]["message"][:70]
        group_id = sha256("\0".join(templates[index] for index in indexes).encode()).hexdigest()[:16]
        clusters.append({
            "id": f"pattern-{group_id}",
            "title": label[0].upper() + label[1:] if label else "Unlabeled log pattern",
            "description": f"{len(matching)} warning or error events share this message theme.",
            "count": len(matching),
            "keywords": keywords,
            "messages": [message for message, _ in counts.most_common(4)],
            "severity_distribution": dict(Counter(event["severity"] for event in matching)),
            "first_seen": matching[0]["timestamp"],
            "last_seen": matching[-1]["timestamp"],
            "services": sorted({event["service"] for event in matching}),
            "event_ids": [event["id"] for event in matching],
        })
    return sorted(clusters, key=lambda cluster: (-cluster["count"], cluster["id"]))
