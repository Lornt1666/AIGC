from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from src.infrastructure.credentials.regional_secret_manager import (
    REGION,
    RegionalSecretError,
    RegionalSecretManagerResolver,
    _crc32c,
)
from src.webapp.nexus_runtime_api import (
    NexusRuntimeConfig,
    NexusRuntimeDependencies,
    create_app,
)


PROJECT = "aigc-stage"
REVISION = "a" * 40
DIGEST = "sha256:" + "b" * 64
AUTHORIZATION_DIGEST = "c" * 64
SECRET_REF = (
    f"projects/{PROJECT}/locations/northamerica-northeast1/"
    "secrets/runtime-control-dsn/versions/7"
)


class FakeResolver:
    def __init__(self) -> None:
        self.access_calls = 0
        self.parser = RegionalSecretManagerResolver(
            expected_project_id=PROJECT,
            client_factory=lambda _endpoint: None,
        )

    def parse_reference(self, reference: str):
        return self.parser.parse_reference(reference)

    def resolve_text(self, reference: str) -> str:
        self.parse_reference(reference)
        self.access_calls += 1
        return "opaque-fixture-value"


class FakeControlStore:
    def __init__(self, *, emergency_active: bool = False) -> None:
        self.emergency_active = emergency_active

    def healthcheck(self):
        return SimpleNamespace(
            ok=True,
            durable=True,
            backend="postgresql",
            emergency_active=self.emergency_active,
            stop_epoch=4,
        )


def config(*, role: str = "operator", secret_ref: str | None = None) -> NexusRuntimeConfig:
    return NexusRuntimeConfig(
        project_id=PROJECT,
        runtime_role=role,
        release_revision=REVISION,
        image_digest=DIGEST,
        region=REGION,
        deployment_authorization_sha256=AUTHORIZATION_DIGEST,
        live_provider_execution_enabled=False,
        production_activation=False,
        runtime_control_dsn_secret_ref=(
            SECRET_REF if role == "operator" and secret_ref is None else secret_ref or ""
        ),
    )


def dependencies(*, emergency_active: bool = False):
    resolver = FakeResolver()
    deps = NexusRuntimeDependencies(
        config=config(),
        secret_resolver=resolver,
        control_store_factory=lambda _value: FakeControlStore(
            emergency_active=emergency_active
        ),
    )
    return deps, resolver


def test_health_does_not_access_secret_or_provider():
    deps, resolver = dependencies()
    response = TestClient(create_app(deps)).get("/health")
    assert response.status_code == 200
    assert response.json()["runtime_role"] == "operator"
    assert response.json()["live_model_call_performed"] is False
    assert resolver.access_calls == 0


def test_operator_readiness_binds_release_image_authorization_and_durable_control():
    deps, resolver = dependencies()
    client = TestClient(create_app(deps))
    response = client.get("/ready")
    body = response.json()
    assert response.status_code == 200
    assert body["ready"] is True
    assert body["project_id"] == PROJECT
    assert body["runtime_role"] == "operator"
    assert body["release_revision"] == REVISION
    assert body["image_digest"] == DIGEST
    assert body["deployment_authorization_sha256"] == AUTHORIZATION_DIGEST
    assert body["runtime_control_backend"] == "postgresql"
    assert body["live_provider_execution_enabled"] is False
    assert resolver.access_calls == 1
    assert client.get("/ready").status_code == 200
    assert resolver.access_calls == 1


def test_provider_free_judge_is_ready_without_secret_or_database_access():
    resolver = FakeResolver()
    deps = NexusRuntimeDependencies(
        config=config(role="judge"),
        secret_resolver=resolver,
        control_store_factory=lambda _value: pytest.fail("judge opened a control store"),
    )
    client = TestClient(create_app(deps))
    body = client.get("/ready").json()
    assert body["ready"] is True
    assert body["runtime_role"] == "judge"
    assert body["provider_capable"] is False
    assert body["runtime_control_backend"] == "not_applicable"
    assert resolver.access_calls == 0
    observed = client.get("/observability").json()
    assert observed["secret_reference_configured"] is False
    assert observed["provider_calls_performed"] == 0


def test_judge_rejects_secret_reference_and_live_provider_flag():
    resolver = FakeResolver()
    with pytest.raises(ValueError, match="must not receive"):
        config(role="judge", secret_ref=SECRET_REF).validate(resolver)
    unsafe = NexusRuntimeConfig(
        **{
            **config(role="judge").__dict__,
            "live_provider_execution_enabled": True,
        }
    )
    with pytest.raises(ValueError, match="cannot enable live provider"):
        unsafe.validate(resolver)


def test_readiness_fails_closed_without_valid_exact_release_identity():
    deps, _resolver = dependencies()
    deps.config = NexusRuntimeConfig(
        **{
            **config().__dict__,
            "release_revision": "release/aigc-nexus-v1",
        }
    )
    response = TestClient(create_app(deps)).get("/ready")
    assert response.status_code == 503
    assert response.json()["ready"] is False


def test_operator_readiness_fails_closed_during_emergency_stop():
    deps, _resolver = dependencies(emergency_active=True)
    response = TestClient(create_app(deps)).get("/ready")
    assert response.status_code == 503
    assert response.json()["failure_class"] == "RuntimeError"


def test_observability_exposes_metadata_not_secret_reference_or_value():
    deps, _resolver = dependencies()
    body = TestClient(create_app(deps)).get("/observability").json()
    assert body["secret_values_exposed"] is False
    assert body["provider_calls_performed"] == 0
    assert body["authorization_digest_configured"] is True
    assert SECRET_REF not in str(body)
    assert "opaque-fixture-value" not in str(body)


def test_regional_secret_manager_requires_exact_project_montreal_numeric_version():
    resolver = RegionalSecretManagerResolver(
        expected_project_id=PROJECT,
        client_factory=lambda _endpoint: None,
    )
    metadata = resolver.parse_reference(SECRET_REF)
    assert metadata.project_id == PROJECT
    assert metadata.location == REGION
    assert metadata.version == "7"
    assert resolver.endpoint == "secretmanager.northamerica-northeast1.rep.googleapis.com"
    with pytest.raises(RegionalSecretError):
        resolver.parse_reference(
            "projects/aigc-other/locations/northamerica-northeast1/secrets/runtime/versions/7"
        )
    with pytest.raises(RegionalSecretError):
        resolver.parse_reference(
            "projects/aigc-stage/locations/us-central1/secrets/runtime/versions/7"
        )
    with pytest.raises(RegionalSecretError):
        resolver.parse_reference(
            "projects/aigc-stage/locations/northamerica-northeast1/secrets/runtime/versions/latest"
        )


def test_regional_secret_response_must_match_exact_name_and_crc32c():
    data = b"opaque-fixture-value"

    class Client:
        def __init__(self, *, response_name: str = SECRET_REF, checksum: int | None = None):
            self.response_name = response_name
            self.checksum = _crc32c(data) if checksum is None else checksum

        def access_secret_version(self, *, request):
            assert request == {"name": SECRET_REF}
            return SimpleNamespace(
                name=self.response_name,
                payload=SimpleNamespace(data=data, data_crc32c=self.checksum),
            )

    good = RegionalSecretManagerResolver(
        expected_project_id=PROJECT,
        client_factory=lambda _endpoint: Client(),
    )
    assert good.resolve_text(SECRET_REF) == data.decode()
    wrong_name = RegionalSecretManagerResolver(
        expected_project_id=PROJECT,
        client_factory=lambda _endpoint: Client(response_name=SECRET_REF.replace("/7", "/8")),
    )
    with pytest.raises(RegionalSecretError, match="name mismatch"):
        wrong_name.resolve_text(SECRET_REF)
    wrong_checksum = RegionalSecretManagerResolver(
        expected_project_id=PROJECT,
        client_factory=lambda _endpoint: Client(checksum=0),
    )
    with pytest.raises(RegionalSecretError, match="checksum mismatch"):
        wrong_checksum.resolve_text(SECRET_REF)
