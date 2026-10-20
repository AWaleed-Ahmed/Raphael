from raphael_agent.patch.image_provenance import resolve_approved_image_replacement


def _signature():
    return {
        "class": "bad_image_reference",
        "normalized": {
            "resource_kind": "Deployment",
            "resource_name": "payments-api",
            "container": "api",
            "attributes": {"image": "ghcr.io/acme/payments-api:does-not-exist", "image_pull_cause": "not_found", "evidence_source": "runtime", "owner_verified": True, "container_type": "regular"},
        },
    }


def _baseline(**overrides):
    row = {
        "healthy_trace_id": "healthy-1",
        "company_id": "company-a", "client_id": "client-a",
        "verified_healthy": True,
        "is_last_known_good": True,
        "source_commit_sha": "a" * 40,
        "repository": "acme/payments",
        "service_name": "payments",
        "environment": "staging",
        "runtime_identity": {
            "resource_kind": "Deployment",
            "resource_name": "payments-api",
            "container_images": {
                "api": "ghcr.io/acme/payments-api@sha256:" + "b" * 64,
            },
        },
    }
    row.update(overrides)
    return row


def _resolve(baselines):
    return resolve_approved_image_replacement(
        _signature(), baselines, company_id="company-a", client_id="client-a", repository="acme/payments",
        service_name="payments", environment="staging",
    )


def test_resolves_digest_from_matching_verified_last_known_good():
    replacement = _resolve([_baseline()])

    assert replacement["image"] == "ghcr.io/acme/payments-api@sha256:" + "b" * 64
    assert replacement["resource_name"] == "payments-api"
    assert replacement["container_name"] == "api"
    assert replacement["source"]["source_commit_sha"] == "a" * 40


def test_rejects_baseline_that_is_not_verified_or_last_known_good():
    assert _resolve([_baseline(is_last_known_good=False)]) is None
    assert _resolve([_baseline(verified_healthy=False)]) is None


def test_rejects_wrong_repository_service_environment_resource_or_container():
    assert _resolve([_baseline(repository="other/payments")]) is None
    assert _resolve([_baseline(service_name="other")]) is None
    assert _resolve([_baseline(environment="production")]) is None
    assert _resolve([_baseline(runtime_identity={"resource_kind": "Deployment", "resource_name": "other", "container_images": {"api": "ghcr.io/acme/payments-api:1"}})]) is None
    assert _resolve([_baseline(runtime_identity={"resource_kind": "Deployment", "resource_name": "payments-api", "container_images": {"worker": "ghcr.io/acme/payments-api:1"}})]) is None


def test_rejects_image_from_another_repository_or_conflicting_baselines():
    other_repo = _baseline(runtime_identity={
        "resource_kind": "Deployment", "resource_name": "payments-api",
        "container_images": {"api": "ghcr.io/other/service:1"},
    })
    conflicting = _baseline(runtime_identity={
        "resource_kind": "Deployment", "resource_name": "payments-api",
        "container_images": {"api": "ghcr.io/acme/payments-api:2"},
    })

    assert _resolve([other_repo]) is None
    assert _resolve([_baseline(), conflicting]) is None


def test_rejects_unknown_or_malformed_commit_provenance():
    for sha in ('unknown', 'abc123', 'z' * 40, None, 123):
        assert _resolve([_baseline(source_commit_sha=sha)]) is None


def test_rejects_unknown_or_missing_replacement_scope():
    assert _resolve([_baseline(environment="unknown")]) is None
    assert _resolve([_baseline(service_name="unknown")]) is None
    assert _resolve([_baseline(repository="unknown")]) is None


def test_malformed_rows_do_not_hide_a_valid_baseline():
    malformed = [None, _baseline(runtime_identity='invalid'),
                 _baseline(runtime_identity={'container_images': 'invalid'})]
    assert _resolve(malformed + [_baseline()]) is not None
    assert _resolve(malformed) is None


def test_rejects_missing_or_wrong_tenant_and_conflicting_commit():
    for field in ('company_id', 'client_id'):
        assert _resolve([_baseline(**{field: 'other'})]) is None
        assert _resolve([_baseline(**{field: None})]) is None
    assert _resolve([_baseline(), _baseline(source_commit_sha='c' * 40)]) is None


def test_rejects_conflicting_namespace_or_cluster_identity():
    for field in ('namespace', 'cluster'):
        baseline = _baseline()
        baseline['runtime_identity'][field] = 'other'
        assert _resolve([baseline]) is None


def test_rejects_malformed_trace_id_and_conflicting_release_commit():
    for identity in (None, {}, 42, ''):
        assert _resolve([_baseline(healthy_trace_id=identity)]) is None
    assert _resolve([_baseline(git_sha='c' * 40)]) is None
