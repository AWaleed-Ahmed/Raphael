# Next three implementation tasks

Planning checkpoint: 2026-10-04, `docs/contributor-handoff` (updated after #37).

#33 and #34 are implemented and tested locally; review, commit/push, hosted proof, and live baseline verification remain outstanding. #30 is still claimed by its existing workstream. The next three items here are handoff items 4–6, not a replacement for #30's prerequisites. These plans do not claim implementation ownership of the Ignis tasks.

## 1. Raphael #37 — readable image-gap presentation

**Status: implemented locally on `docs/contributor-handoff`; focused tests pass.** Detailed cases and result are recorded in `docs/implementation-review-2026-10-04.md`.

**Goal:** A reviewer can see all images with unresolved digests under one explanatory prefix, while other fidelity gaps remain visible.

1. Inspect `agent/raphael_agent/publish/pr_body.py` and the current per-image gap test in `agent/tests/test_publish.py`. Identify the exact existing image-gap prefix and keep matching limited to that recognized format.
2. Group matching messages for display under one prefix with an image list. Preserve full references, including registry ports, tags, and digests. Keep non-image gaps in their original order; do not rewrite the stored fidelity report.
3. Add cases for one image, multiple images, mixed image/non-image gaps, duplicate references, registry ports, and no gaps. Check that rendering does not mutate its input and that a remaining gap does not acquire a full-validation claim.
4. Record the before/after PR-body examples and test results in the implementation review note. Run the focused publish tests, then the agent suite if rendering touches shared publishing behavior.

**Done when:** The PR body has one image-gap prefix, every unresolved image is visible, other gaps are preserved, and the persisted per-image evidence and validation flags are unchanged.

**Coordination:** Display changes can proceed on this Raphael branch. Fidelity schema/data changes overlap #30 and require coordination; they are unnecessary for this task.

## 2. Ignis #11 — real image-pull failure detection

**Goal:** Classify real missing-image failures using runtime evidence, with explicit uncertainty for authentication, network, and rate-limit failures.

1. Inspect Ignis's current observation/backend code and the issue before editing. Trace how runtime image status, events, and container identity become a failure signature. List which cases today rely on known-bad string patterns.
2. Agree the initial evidence source. Prefer existing sandbox Pod status/events where they supply enough information; add registry queries only if a documented evidence gap requires them. Keep credentials out of logs and stay within the authorized sandbox.
3. Distinguish confirmed missing image/tag from authentication failure, timeout/DNS/connectivity failure, and throttling. Record evidence with the exact affected workload/container/image. Ambiguous pull failure must not authorize a guessed image replacement.
4. Add deterministic observation fixtures for each classification and multi-container targeting. Use an isolated registry and disposable kind workload to cross-check valid-image, nonexistent-tag, and unauthorized-pull controls; avoid relying on public registry availability for every test.
5. Verify how Raphael consumes the resulting signatures. Preserve #34's provenance requirement: better detection alone must not authorize an image repair. Report the Ignis diff and evidence before merge/release; update Raphael pins only after an approved release.

**Done when:** Real-runtime controls demonstrate the claimed distinctions, ambiguous failures refuse safely, and mock evidence is reported separately from real-backend proof.

**Coordination:** Obtain the existing #30 owner's status before changing shared observation/backend paths. Use a reviewed Ignis development branch; do not change public schemas or release pins independently. If the current signature format suffices, prefer an implementation-only release.

## 3. Ignis #13 — clone line-ending fidelity policy

**Goal:** Make repository checkout and render behavior deliberate and reproducible across environments without changing global Git configuration.

1. Investigate before coding. Build disposable repositories containing LF, CRLF, mixed endings, explicit `.gitattributes`, and binary files. Compare committed blob bytes, cloned worktree bytes, and rendered bytes using the current Ignis clone path.
2. Write a decision choosing between exact blob preservation and Git attribute-controlled worktree normalization. Account for repository attributes and existing render-boundary LF normalization. Recommend the smallest change justified by the experiment; a documented policy may be sufficient if current behavior already matches it.
3. If code is needed, apply settings only to the owned clone or Git invocation. Preserve customer files and binary content. Keep checkout policy separate from render normalization so the same rule is not applied twice.
4. Add cross-environment checks for the agreed byte behavior, attributes, binary preservation, and patch diff size. Include a conflict case where caller Git settings differ from repository attributes.
5. Record byte comparisons, the selected policy, and test results. Re-run the existing forced-CRLF evaluation/verifier and contract drift check where applicable, then propose the Ignis change for review.

**Done when:** The policy is recorded, fixtures produce the agreed checkout/render bytes, binaries are unchanged, and patch diffs remain minimal across the tested environments.

**Coordination:** Read-only experiments can start independently. Runtime clone/render edits overlap #30's fixture/recovery work and require coordination. Existing render-boundary normalization is already implemented; do not redo it.

### Initial read-only Ignis findings

- On the available Ignis checkout (`fix/kubectl-cluster-backend-name`), #11 has live `ImagePullBackOff`/`ErrImagePull` status handling, but all those failures currently map to `bad_image_reference`; the rendered-YAML string heuristic is checked first and can take precedence. The parser captures Pod container image, waiting reason/message, but the analysis does not yet distinguish not-found from auth, network, or throttling causes.
- The clone path in `controller/src/gitclone.rs` runs ordinary `git init`, `fetch`, and `checkout`/fallback `git clone` without setting clone-local line-ending configuration. #13 therefore needs a controlled byte-comparison experiment before choosing a policy.
- The checkout is clean and on the existing feature branch. No Ignis files were changed. This checkout contains no contributor handoff file with #30 ownership details, so implementation coordination still needs the current owner's status before editing shared controller paths.

## Execution order and review evidence

Start with #37 because it is a contained Raphael rendering change. Investigate #11 and #13 next, coordinate the Ignis edits, and review each change separately. For every task, append exact test commands, fixture/revision identifiers, backend, outcomes, and limitations to the review note. Unit results alone do not close real-backend or hosted-proof milestones.
