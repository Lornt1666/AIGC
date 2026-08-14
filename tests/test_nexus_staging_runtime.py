from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from src.infrastructure.credentials.regional_secret_manager import REGION, RegionalSecretError, RegionalSecretManagerResolver
from src.webapp.nexus_runtime_api import NexusRuntimeConfig, NexusRuntimeDependencies, create_app

REVISION = "a" * 40
DIGEST = "sha256:" + "b" * 64
SECRET_REF = "projects/aigc-stage/locations/northamerica-northeast1/secrets/runtime-control-dsn/versions/7"

class FakeResolver:
    def __init__(self) -> None:
        self.access_calls = 0
        self.parser = RegionalSecretManagerResolver(client_factory=lambda _endpoint: None)

    def parse_reference(self, reference: str):
        return self.parser.parse_reference(reference)

    def resolve_text(self, reference: str) -> str:
        self.parse_reference(reference)
        self.access_calls += 1
        return "opaque-fixture-value"

class FakeControlStore:
    def healthcheck(self):
        return SimpleNamespace(ok=True, durable=True, backend="postgresql", emergency_active=False, stop_epoch=4)

def dependencies():
    resolver = FakeResolver()
    deps = NexusRuntimeDependencies(
        config=NexusRuntimeConfig(
            release_revision=REVISION,
            image_digest=DIGEST,
            region=REGION,
            runtime_control_dsn_secret_ref=SECRET_REF,
        ),
        secret_resolver=resolver,
        control_store_factory=lambda _value: FakeControlStore(),
    )
    return deps, resolver

def test_health_does_not_access_secret_or_provider():
    deps, resolver = dependencies()
    response = TestClient(create_app(deps)).get("/health")
    assert response.status_code == 200
    assert response.json()["live_model_call_performed"] is False
    assert resolver.access_calls == 0

def test_readiness_binds_exact_release_image_region_and_durable_control_health():
    deps, resolver = dependencies()
    client = TestClient(create_app(deps))
    response = client.get("/ready")
    body = response.json()
    assert response.status_code == 200
    assert body["ready"] is True
    assert body["release_revision"] == REVISION
    assert body["image_digest"] == DIGEST
    assert body["region"] == REGION
    assert body["runtime_control_backend"] == "postgresql"
    assert resolver.access_calls == 1
    assert client.get("/ready").status_code == 200
    assert resolver.access_calls == 1

def test_readiness_fails_closed_without_valid_exact_release_identity():
    deps, _resolver = dependencies()
    deps.config = NexusRuntimeConfig(
        release_revision="release/aigc-nexus-v1",
        image_digest=DIGEST,
        region=REGION,
        runtime_control_dsn_secret_ref=SECRET_REF,
    )
    response = TestClient(create_app(deps)).get("/ready")
    assert response.status_code == 503
    assert response.json()["ready"] is False

def test_observability_exposes_metadata_not_secret_reference_or_value():
    deps, _resolver = dependencies()
    payload = TestClient(create_app(deps)).get("/observability").json()
    assert payload["secret_values_exposed"] is False
    assert payload["provider_calls_performed"] == 0
    assert SECRET_REF not in str(payload)
    assert "opaque-fixture-value" not in str(payload)

def test_regional_secret_manager_requires_exact_montreal_numeric_version():
    resolver = RegionalSecretManagerResolver(client_factory=lambda _endpoint: None)
    metadata = resolver.parse_reference(SECRET_REF)
    assert metadata.location == REGION
    assert metadata.version == "7"
    assert resolver.endpoint == "secretmanager.northamerica-northeast1.rep.googleapis.com"
    with pytest.raises(RegionalSecretError):
        resolver.parse_reference("projects/aigc-stage/locations/us-central1/secrets/runtime/versions/7")
    with pytest.raises(RegionalSecretError):
        resolver.parse_reference("projects/aigc-stage/locations/northamerica-northeast1/secrets/runtime/versions/latest")
