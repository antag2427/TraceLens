# Machine learning pipeline

Each run uses stored log events as observations. The feature stage produces numeric vectors per service and time window. The anomaly stage scores the vectors. A separate text pipeline groups error patterns, and incident correlation consumes both outputs along with raw event context.

## Feature families

| Feature family | Purpose |
| --- | --- |
| Time window and service | Place events on a shared clock while preserving each service's traffic and error baseline |
| Traffic volume and change | Surface sudden growth, drop-offs and consecutive-window differences |
| Severity counts and error fraction | Distinguish warning noise and error spikes from a normal rise in traffic |
| Unique error fingerprints | Count distinct failure patterns and distinguish concentrated repetition from diverse errors |
| Message length | Detect changes in the shape of emitted events, including sudden verbose failures |
| Timeout and dependency-related terms | Capture shifts in recurring logistical failure signals |
| Rolling or historical baselines | Compare current behavior with nearby historical observations |

See `backend/app/features.py` for exact feature names. Event-volume delta compares with the previous window. Rolling event and error counts average six prior windows. The implementation represents bounded internal inactivity by retaining selected empty windows between observed activity. Values describe log emissions. Missing logs can reflect inactivity, collection interruptions, or a genuinely quiet service.

## Isolation Forest and fallback

Isolation Forest repeatedly chooses a feature and a random split. Samples set apart by short paths are unusual relative to fitted samples. TraceLens combines model output with statistical deviations and retains the underlying features and explanations for review. The statistical path compares with up to 24 prior service windows using the median and median absolute deviation with a floor on scale. With fewer than four prior observations, critical activity or multiple errors can still be flagged. By default Isolation Forest fits 100 trees per service after 12 windows if the features vary. Pandas organizes the named features and NumPy supplies the numeric model matrix. Contamination affects how many fitted observations the model tends to label unusual, while the chosen window size affects both noise and onset resolution.

## TF-IDF and clustering

The text pipeline uses normalized warning and error templates and removes common placeholder tokens before vectorization. TF-IDF emphasizes terms that are informative within the corpus. Up to 400 templates are grouped into connected components using cosine similarity with a default threshold of 0.26. Larger corpora use MiniBatchKMeans, which updates cluster centroids in batches. A corpus with no extractable vocabulary falls back to template groups. Its cluster labels are local to the analysis context. Representative messages, keywords, severities, services and occurrence ranges make each group inspectable. Empty or low-diversity input needs special handling because the corpus may have little vocabulary or too few distinct vectors.

## Interpretation and experiments

An anomaly identifies an unusual service window. A cluster identifies recurring text. An incident correlates potentially related evidence. A hypothesis ranks possible initiating explanations. Use the demo to trace one event through all four stages, then rerun with another supported window size and compare alert counts, incident start times and candidate ranks. Compare outputs on the same input when evaluating configuration changes.

