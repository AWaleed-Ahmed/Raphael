"""Image-pull cause and backend gates cannot be overridden by patch models."""
import pytest

from raphael_agent.image_pull import image_pull_block_reason, image_pull_repair_allowed
from raphael_agent.patch import propose_patch
from raphael_agent.patch.templates import TemplateRefusal


def signature(cause="not_found", source="runtime"):
    return {"class": "bad_image_reference", "normalized": {
        "reason": "ImagePullBackOff", "resource_kind": "Deployment",
        "resource_name": "app", "container": "app", "attributes": {
            "image": "registry.example/app:v7", "image_pull_cause": cause,
            "evidence_source": source, "owner_verified": True, "container_type": "regular",
        },
    }}


@pytest.mark.parametrize("cause", ["auth", "network", "rate_limited", "unknown"])
def test_non_absence_causes_refuse_even_direct_patch_calls(cause):
    run = {"failure_signature": signature(cause), "trigger": {"kind": "github_issue"}}
    assert image_pull_block_reason(run)
    with pytest.raises(TemplateRefusal):
        propose_patch(run)


def test_fixture_source_requires_recorded_mock_backend():
    fixture = signature(source="mock_fixture")
    assert not image_pull_repair_allowed(fixture)
    assert not image_pull_repair_allowed(fixture, "kubectl")
    assert image_pull_repair_allowed(fixture, "mock")


def test_legacy_signature_is_unverified():
    legacy = signature()
    legacy["normalized"]["attributes"] = {"image": "registry.example/app:v7"}
    assert image_pull_block_reason({"failure_signature": legacy}) == "image_pull_evidence_unverified"
