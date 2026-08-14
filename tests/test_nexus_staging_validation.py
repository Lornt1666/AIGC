from __future__ import annotations

from types import SimpleNamespace

import pytest

import scripts.validate_nexus_staging_runtime as validator


RELEASE_SHA = "a" * 40
IMAGE_DIGEST = "sha256:" + "b" * 64


def target(**updates):
    values = {
        "project_id": "aigc-stage-12345",
        "region": validator.REGION,
        "service": "aigc-operator-stg",
        "revision": "aigc-operator-stg-00001-abc",
        "release_sha": RELEASE_SHA,
        "image_digest": IMAGE_DIGEST,
        "candidate_url": "https://candidate-a1b2c3---aigc-operator-stg-xyz.nn.a.run.app",
        "audience": "https://aigc-operator-stg-xyz.nn.a.run.app",
    }
    values.update(updates)
    return validator.VerifiedCandidateTarget(**values)


class Response:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeClient:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url, headers=None):
        if headers is None:
            return Response(403, {"detail": "denied"})
        if url.endswith("/health"):
            return Response(200, {"ok": True})
        if url.endswith("/ready"):
            return Response(200, {"ready": True})
        if url.endswith("/observability"):
            return Response(200, {"secret_values_exposed": False})
        return Response(404, {"detail": "not found"})


def test_candidate_validation_records_bounded_load_security_and_reconciliation(monkeypatch):
    monkeypatch.setattr(validator.httpx, "Client", lambda **_kwargs: FakeClient())
    monkeypatch.setattr(
        validator.httpx,
        "get",
        lambda *_args, **_kwargs: Response(200, {"ready": True}),
    )
    result = validator.validate_candidate(
        target=target(),
        requests=8,
        concurrency=2,
        token_supplier=lambda _audience: "opaque-test-token",
    )
    assert result["authenticated_health"] == "PASS"
    assert result["authenticated_readiness"] == "PASS"
    assert result["unauthenticated_access"] == "DENIED"
    assert result["invalid_route"] == "FAIL_CLOSED"
    assert result["load_requests"] == 8
    assert result["load_failures"] == 0
    assert result["canonical_reconciliation_boundary"] == "PASS"
    assert result["state_advanced"] is False
    assert result["deployed_fault_injection_performed"] is False
    assert result["provider_calls_performed"] == 0


def test_candidate_validation_rejects_unbounded_load():
    with pytest.raises(ValueError, match="load bounds"):
        validator.validate_candidate(
            target=target(),
            requests=201,
            concurrency=1,
            token_supplier=lambda _audience: "opaque-test-token",
        )


def test_candidate_target_rejects_independent_token_destination():
    with pytest.raises(ValueError, match="not bound"):
        target(candidate_url="https://attacker.example.run.app")


def test_candidate_target_rejects_non_cloud_run_origin_and_url_components():
    with pytest.raises(ValueError, match="Cloud Run"):
        target(candidate_url="https://attacker.example.invalid")
    with pytest.raises(ValueError, match="without credentials"):
        target(candidate_url="https://aigc-operator-stg-xyz.nn.a.run.app/steal")


def test_resolver_requires_exact_tag_revision_digest_and_release_label(monkeypatch):
    service = {
        "status": {
            "url": "https://aigc-operator-stg-xyz.nn.a.run.app",
            "traffic": [{
                "tag": "candidate-aaaaaaaa",
                "revisionName": "aigc-operator-stg-00001-abc",
                "url": "https://candidate-aaaaaaaa---aigc-operator-stg-xyz.nn.a.run.app",
            }],
        }
    }
    revision = {
        "metadata": {"labels": {"aigc-release-sha": RELEASE_SHA}},
        "spec": {"containers": [{"image": "northamerica-northeast1-docker.pkg.dev/p/r/i@" + IMAGE_DIGEST}]},
    }
    responses = iter((service, revision))
    monkeypatch.setattr(validator, "_gcloud_json", lambda _command: next(responses))
    resolved = validator.resolve_candidate_target(
        project_id="aigc-stage-12345",
        service="aigc-operator-stg",
        revision="aigc-operator-stg-00001-abc",
        release_sha=RELEASE_SHA,
        image_digest=IMAGE_DIGEST,
    )
    assert resolved.revision == "aigc-operator-stg-00001-abc"
    assert resolved.audience == "https://aigc-operator-stg-xyz.nn.a.run.app"


def test_resolver_rejects_stale_candidate_revision(monkeypatch):
    monkeypatch.setattr(
        validator,
        "_gcloud_json",
        lambda _command: {
            "status": {
                "url": "https://aigc-operator-stg-xyz.nn.a.run.app",
                "traffic": [{
                    "tag": "candidate-aaaaaaaa",
                    "revisionName": "aigc-operator-stg-00000-old",
                    "url": "https://candidate-aaaaaaaa---aigc-operator-stg-xyz.nn.a.run.app",
                }],
            }
        },
    )
    with pytest.raises(validator.NexusStagingValidationError, match="exact tagged"):
        validator.resolve_candidate_target(
            project_id="aigc-stage-12345",
            service="aigc-operator-stg",
            revision="aigc-operator-stg-00001-abc",
            release_sha=RELEASE_SHA,
            image_digest=IMAGE_DIGEST,
        )
