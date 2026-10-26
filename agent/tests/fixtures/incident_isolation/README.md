# Incident isolation source provenance

`public-sources.json` checks the 50 source-linked GitHub issue reports already
retained in `../local_inference/incident_similarity.jsonl`. On 2026-10-26,
49 were verified through GitHub's public issue API. `luxfi/node#143` returned
404 on the original check and retry and is excluded from the searchable index.
The historical query fixture is unchanged; replay may abstain for that query.
No live network request is required by runtime or CI replay.

The verification snapshot records public URLs, titles, timestamps, body hashes
and input snapshot hashes, without copying additional issue bodies. Labels are
marker-derived, not independently confirmed root causes or successful repairs.

The format-2 artifact repeats those 49 indexed reports in four explicitly owned
test partitions: two companies, each with two clients. Tenant/company/client IDs
are synthetic test assignments, unrelated to the public source authors. That is
196 owned test records, not 196 independent incidents or production tenants.
Each partition fits its own TF-IDF vectorizer and matrix. No public/shared
search fallback exists. No historical fix template is asserted for these reports.

`build_scoped_incident_fixture.py` recreates the owned corpus, vocabulary and numerically equivalent index from this
verification snapshot and the original public query fixture. The independent
runtime trust roots must be updated through release review whenever corpus or
ownership bytes change. Customer-supplied joblib files are never accepted.
