# Root cause methodology

TraceLens estimates which service or event pattern may have initiated an incident. A candidate is a service and error fingerprint pair. Its score is the weighted sum of the signals divided by the total configured weight. Scores express relative strength of evidence on a zero-to-one scale. Causal confirmation requires independent evidence.

| Evidence | Default weight | Interpretation |
| --- | ---: | --- |
| Temporal precedence | 0.22 | A candidate surfaced early relative to other related failures. Clock skew and delayed log emission can affect ordering. |
| Anomaly onset | 0.12 | An unusual service window appeared near the beginning of the incident. Bucketing limits time resolution. |
| Severity | 0.17 | Critical events carry more weight. |
| Recurrence | 0.08 | Pattern count relative to the most frequent candidate. |
| Shared traces and requests | 0.13 | Matching identifiers relate activity across services. The match on its own does not determine direction. |
| Dependency evidence | 0.18 | Later failures in configured dependents receive full weight. Inferred relationship evidence receives 0.45 of that weight. |
| Impact | 0.06 | Share of other affected services whose first failure happened later. |
| Propagation | 0.04 | Share of other affected services with both later failures and shared identifiers. |
| Contradicting evidence | Shown in the explanation | Earlier failures elsewhere reduce precedence and impact. Missing identifiers reduce correlation and propagation. The report lists these observations without a separate penalty. |

Start with the observed timeline. Compare the first events, the affected services, and identifiers that connect the events. Then compare each hypothesis's score, supporting evidence, and contrary evidence. Close ranks or sparse evidence warrant multiple working explanations. External metrics, explicit trace spans, or infrastructure records may be needed to confirm which failure initiated the incident.

Read `backend/app/incidents.py` alongside one exported JSON report. Map the candidate fields back to the implementation and check the source event IDs in the log explorer. Two services that produce simultaneous errors with unrelated trace IDs are a useful example of ambiguous evidence.

