from raphael_agent.patch.image_provenance import resolve_approved_image_replacement


def _signature():
    return {
        "class": "bad_image_reference",
        "normalized": {
            "resource_name": "payments-api",
            "container": "api",
            "attributes": {"image": "ghcr.io/acme/payments-api:does-not-exist"},
        },
    }


def _baseline(**overrides):
    row = {
        "healthy_trace_id": "healthy-1",
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
        _signature(), baselines, repository="acme/payments",
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
