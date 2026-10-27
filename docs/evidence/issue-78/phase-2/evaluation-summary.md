# Phase 2 development evaluation

All five capabilities remain deferred. Final held-out approval and quality gates are pending.

| Capability | Cases checked | Learned calls | Rule overrides | Decision |
| --- | ---: | ---: | ---: | --- |
| candidate_ranker | 3 | 2 | 0 | insufficient_evidence |
| failure_classifier | 6 | 4 | 0 | insufficient_evidence |
| incident_similarity | 6 | 6 | 0 | insufficient_evidence |
| patch_selector | 6 | 0 | 0 | blocked |
| trace_anomaly | 3 | 0 | 0 | blocked |

Ranking uses real graph-generated candidates and a maintainer-file development oracle. Other quality metrics remain unscored. See summary.json for exact gates, denominators and blockers.
