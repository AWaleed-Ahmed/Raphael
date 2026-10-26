# Google Online Boutique image-pull fixture

Source: [GoogleCloudPlatform/microservices-demo v0.10.4](https://github.com/GoogleCloudPlatform/microservices-demo/tree/474d0f2eb73d97525234995a40d7781b7923a07d).
`app.yaml` extracts only the `productcatalogservice` Deployment, Service and
ServiceAccount from that commit's `release/kubernetes-manifests.yaml`. The object
bytes, copyright and Apache-2.0 notice are preserved. `upstream.json` records the
source and extracted-file SHA-256 hashes. The upstream license is included.

This is a Google-maintained public sample with an injected absent-image fault,
not a recorded Google production incident. The temporary failing Git fixture
changes only the image tag; the healthy fixture retains the upstream image.
The product catalog serves a local catalog and uses native gRPC health probes,
so this proof does not need the rest of Online Boutique.

The harness independently observes the healthy baseline Pod Ready and its
resolved imageID before supplying its release identity to the existing scoped
loopback REST catalog. That catalog is test infrastructure, not live Supabase
baseline ingestion. The real dispatch, connector, Ignis kubectl controller,
diagnosis, patching and validation paths are used; no model is needed.

Run on the disposable hosted kind runner with `python e2e/run_google_image_proof.py`.
The cross-repository workflow preloads the healthy image and runs both the
missing-baseline refusal and verified-baseline repair. It uploads the baseline,
initial Pod/events/ReplicaSet/Deployment, verified owner identity, real HTTP
traces, runner results and Pod observations under
`kind-remediation-<run_id>/google-productcatalog/`.
