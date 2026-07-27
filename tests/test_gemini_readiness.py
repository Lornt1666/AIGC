from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.gemini_workflow.readiness import (
    CallableProbe,
    GcsObjectMetadataProbe,
    GcsReadProbe,
    ProbeResult,
    ReadinessEvaluator,
    RuntimeControlProbe,
    RuntimeLimitsProbe,
    SecretPresenceProbe,
    VertexModelMetadataProbe,
    app,
    set_readiness_evaluator_override,
)
from src.gemini_workflow.settings import GeminiWorkflowSettings


def settings(tmp_path: Path) -> GeminiWorkflowSettings:
    return GeminiWorkflowSettings(
        enabled=True,
        project_id="example-project",
        location="example-region",
        model="example-model",
        evidence_backend="gcs",
        evidence_path=None,
        evidence_bucket="example-evidence",
        evidence_prefix="product-evidence/gemini",
        environment="production",
        timeout_seconds=30,
        max_output_tokens=1200,
        max_attempts=3,
        source_revision="a" * 40,
        runtime_revision="aigc-gemini-00001",
    )


def test_liveness_never_executes_readiness_probe() -> None:
    calls = 0

    def poison() -> bool:
        nonlocal calls
        calls += 1
        raise AssertionError("liveness must not evaluate dependencies")

    set_readiness_evaluator_override(
        ReadinessEvaluator(
            [CallableProbe("poison", "read_only", poison)]
        )
    )
    try:
        response = TestClient(app).get("/livez")
    finally:
        set_readiness_evaluator_override(None)

    assert response.status_code == 200
    assert response.json()["live"] is True
    assert response.json()["generative_call_performed"] is False
    assert calls == 0


def test_readiness_is_200_only_when_every_probe_passes() -> None:
    evaluator = ReadinessEvaluator(
        [
            CallableProbe("configuration", "local_validation", lambda: True),
            CallableProbe("gcs", "metadata_read", lambda: True),
            CallableProbe("vertex", "metadata_read", lambda: True),
        ]
    )
    set_readiness_evaluator_override(evaluator)
    try:
        response = TestClient(app).get("/readyz")
    finally:
        set_readiness_evaluator_override(None)

    payload = response.json()
    assert response.status_code == 200
    assert payload["ready"] is True
    assert payload["status"] == "ready"
    assert payload["generative_call_performed"] is False
    assert payload["external_action_performed"] is False


def test_readiness_fails_closed_and_sanitizes_probe_exceptions() -> None:
    secret_canary = "do-not-return-this-secret"

    def failing_probe() -> bool:
        raise RuntimeError(secret_canary)

    set_readiness_evaluator_override(
        ReadinessEvaluator(
            [CallableProbe("dependency", "metadata_read", failing_probe)]
        )
    )
    try:
        response = TestClient(app).get("/readyz")
    finally:
        set_readiness_evaluator_override(None)

    assert response.status_code == 503
    assert response.json()["checks"][0]["detail"] == "probe_failed_closed"
    assert secret_canary not in response.text


def test_isolated_status_authenticates_a_stable_operator_principal(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "AIGC_COMMAND_CENTER_TOKEN",
        "test-command-token-with-sufficient-length",
    )
    monkeypatch.setenv(
        "AIGC_OPERATOR_SUBJECT_KEY",
        "test-subject-binding-key-with-at-least-32-characters",
    )

    response = TestClient(app).get(
        "/api/gemini/status",
        headers={
            "x-aigc-command-token": (
                "test-command-token-with-sufficient-length"
            ),
            "x-aigc-operator-label": "readiness-test-operator",
        },
    )

    assert response.status_code == 200
    assert response.json()["external_action_allowed"] is False


def test_readiness_cache_avoids_probe_storms() -> None:
    now = [100.0]
    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        return True

    evaluator = ReadinessEvaluator(
        [CallableProbe("dependency", "metadata_read", probe)],
        cache_ttl_seconds=10,
        clock=lambda: now[0],
    )
    assert evaluator.evaluate().ready is True
    assert evaluator.evaluate().ready is True
    assert calls == 1
    now[0] += 11
    assert evaluator.evaluate().ready is True
    assert calls == 2


def test_application_secret_probe_requires_distinct_32_character_values() -> None:
    short = SecretPresenceProbe(
        {
            "AIGC_COMMAND_CENTER_TOKEN": "x" * 31,
            "AIGC_OPERATOR_SUBJECT_KEY": "y" * 32,
        }
    ).check()
    reused = SecretPresenceProbe(
        {
            "AIGC_COMMAND_CENTER_TOKEN": "z" * 32,
            "AIGC_OPERATOR_SUBJECT_KEY": "z" * 32,
        }
    ).check()
    valid = SecretPresenceProbe(
        {
            "AIGC_COMMAND_CENTER_TOKEN": "x" * 32,
            "AIGC_OPERATOR_SUBJECT_KEY": "y" * 32,
        }
    ).check()

    assert short.ready is False
    assert reused.ready is False
    assert valid.ready is True


def test_gcs_probe_is_read_only(tmp_path: Path) -> None:
    class FakeStorageClient:
        def __init__(self) -> None:
            self.calls = []

        def list_blobs(self, bucket, **kwargs):
            self.calls.append((bucket, kwargs))
            return []

    client = FakeStorageClient()
    probe = GcsReadProbe(
        lambda: settings(tmp_path),
        lambda _settings: client,
        timeout_seconds=5,
    )
    result = probe.check()

    assert result.ready is True
    assert result.generative_call_performed is False
    assert result.operation == "cloud_storage_metadata_read"
    assert client.calls == [
        (
            "example-evidence",
            {
                "prefix": "product-evidence/gemini/",
                "max_results": 1,
                "timeout": 5,
                "retry": None,
            },
        )
    ]


def test_exact_gcs_readiness_sentinel_avoids_bucket_listing() -> None:
    class FakeBlob:
        generation = 17

        def __init__(self) -> None:
            self.reload_calls = []

        def reload(self, **kwargs):
            self.reload_calls.append(kwargs)

    class FakeBucket:
        def __init__(self, blob: FakeBlob) -> None:
            self._blob = blob
            self.names = []

        def blob(self, name):
            self.names.append(name)
            return self._blob

    class FakeStorageClient:
        def __init__(self, bucket: FakeBucket) -> None:
            self._bucket = bucket
            self.bucket_names = []
            self.list_calls = 0

        def bucket(self, name):
            self.bucket_names.append(name)
            return self._bucket

        def list_blobs(self, *_args, **_kwargs):
            self.list_calls += 1
            raise AssertionError("readiness must not list evidence objects")

    blob = FakeBlob()
    bucket = FakeBucket(blob)
    client = FakeStorageClient(bucket)
    result = GcsObjectMetadataProbe(
        lambda: "example-project",
        lambda: "example-evidence",
        lambda: "product-evidence/gemini/readiness.json",
        lambda _project: client,
        timeout_seconds=5,
        name="gcs_evidence_read",
    ).check()

    assert result.ready is True
    assert result.operation == "cloud_storage_generation_metadata_read"
    assert client.bucket_names == ["example-evidence"]
    assert bucket.names == ["product-evidence/gemini/readiness.json"]
    assert blob.reload_calls == [{"timeout": 5, "retry": None}]
    assert client.list_calls == 0


def test_vertex_probe_reads_metadata_without_generation(tmp_path: Path) -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.get_calls = []
            self.generation_calls = 0

        def get(self, *, model):
            self.get_calls.append(model)
            return type("Model", (), {"name": model})()

        def generate_content(self, **_kwargs):
            self.generation_calls += 1
            raise AssertionError("readiness must not generate content")

    fake_models = FakeModels()
    client = type("Client", (), {"models": fake_models})()
    probe = VertexModelMetadataProbe(
        lambda: settings(tmp_path),
        lambda _settings, _timeout: client,
        timeout_seconds=5,
    )
    result = probe.check()

    assert result.ready is True
    assert result.operation == "vertex_model_metadata_read"
    assert fake_models.get_calls == ["example-model"]
    assert fake_models.generation_calls == 0


def test_runtime_control_probe_only_executes_healthcheck(
    tmp_path: Path,
) -> None:
    class FakeControlStore:
        def __init__(self) -> None:
            self.healthcheck_calls = 0
            self.mutation_calls = 0

        def healthcheck(self):
            self.healthcheck_calls += 1
            return type(
                "Health",
                (),
                {
                        "ok": True,
                        "durable": True,
                        "backend": "postgresql",
                        "emergency_active": False,
                },
            )()

        def activate_emergency_stop(self, **_kwargs):
            self.mutation_calls += 1
            raise AssertionError("readiness must not mutate runtime control")

    store = FakeControlStore()
    probe = RuntimeControlProbe(
        lambda: settings(tmp_path),
        lambda _settings: store,
    )
    result = probe.check()

    assert result.ready is True
    assert result.operation == "cloud_sql_readiness_query"
    assert result.generative_call_performed is False
    assert result.external_action_performed is False
    assert store.healthcheck_calls == 1
    assert store.mutation_calls == 0


def test_runtime_control_probe_rejects_non_durable_test_store(
    tmp_path: Path,
) -> None:
    health = type(
        "Health",
        (),
        {
            "ok": True,
            "durable": False,
            "backend": "memory_test_only",
        },
    )()
    store = type("Store", (), {"healthcheck": lambda _self: health})()

    result = RuntimeControlProbe(
        lambda: settings(tmp_path),
        lambda _settings: store,
    ).check()

    assert result.ready is False
    assert result.detail == "runtime_control_read_failed"


def test_runtime_limits_contract_is_valid() -> None:
    result = RuntimeLimitsProbe(
        Path("config/gemini_runtime_limits.json")
    ).check()

    assert result.ready is True
    assert result.operation == "local_file_validation"


def test_probe_cannot_claim_generation_or_external_action() -> None:
    class UnsafeProbe:
        name = "unsafe"

        def check(self) -> ProbeResult:
            return ProbeResult(
                name=self.name,
                ready=True,
                detail="unsafe",
                operation="generation",
                generative_call_performed=True,
                external_action_performed=True,
            )

    report = ReadinessEvaluator([UnsafeProbe()]).evaluate()

    assert report.ready is False
    assert report.checks[0].detail == "probe_failed_closed"
    assert report.generative_call_performed is False
    assert report.external_action_performed is False
