from __future__ import annotations

import logging

import pytest

from src.gemini_workflow.secret_broker import SecretBroker, SecretBrokerError
from src.gemini_workflow.secret_broker import OmegaXSecretAccess


class FakeSecretClient:
    def access_secret_version(self, *, request):
        assert request["name"].endswith("/versions/7")
        payload = type("Payload", (), {"data": b"resolved-value"})()
        return type("Response", (), {"payload": payload})()


def test_secret_broker_requires_exact_version_and_logs_no_value(caplog) -> None:
    access = OmegaXSecretAccess.from_environment(
        project_id="example-project",
        environ={
            "AIGC_OPERATOR_TOKEN_SECRET_REF": (
                "projects/example-project/secrets/operator-token/versions/7"
            ),
            "AIGC_DEPLOYMENT_AUTHORIZATION_SHA256": "a" * 64,
        },
        client=FakeSecretClient(),
    )
    with caplog.at_level(logging.INFO):
        value, receipt = access.resolve(
            "gemini-operator-authentication"
        )

    assert value == "resolved-value"
    assert receipt.exact_version == "7"
    assert receipt.value_logged is False
    assert receipt.chain[0] == "Omega-X Orchestrator"
    assert receipt.audit_sink == "cloud_logging_metadata_only"
    assert "resolved-value" not in caplog.text


def test_secret_broker_rejects_aliases_and_cross_project_refs() -> None:
    with pytest.raises(SecretBrokerError, match="exact numeric"):
        OmegaXSecretAccess.from_environment(
            project_id="example-project",
            environ={
                "AIGC_OPERATOR_TOKEN_SECRET_REF": (
                    "projects/example-project/secrets/operator-token/"
                    "versions/latest"
                ),
                "AIGC_DEPLOYMENT_AUTHORIZATION_SHA256": "a" * 64,
            },
            client=FakeSecretClient(),
        ).resolve("gemini-operator-authentication")
    with pytest.raises(SecretBrokerError, match="does not match"):
        OmegaXSecretAccess.from_environment(
            project_id="example-project",
            environ={
                "AIGC_OPERATOR_TOKEN_SECRET_REF": (
                    "projects/other-project/secrets/operator-token/versions/7"
                ),
                "AIGC_DEPLOYMENT_AUTHORIZATION_SHA256": "a" * 64,
            },
            client=FakeSecretClient(),
        ).resolve("gemini-operator-authentication")


def test_low_level_broker_rejects_direct_non_agent_access() -> None:
    broker = SecretBroker(
        project_id="example-project",
        client=FakeSecretClient(),
    )
    with pytest.raises(SecretBrokerError, match="Ultra-Secrets"):
        broker.resolve_text(
            "projects/example-project/secrets/operator-token/versions/7",
            purpose="gemini-operator-authentication",
            delegated_by="web-app",
            manifest_sha256="b" * 64,
            deployment_authorization_sha256="a" * 64,
        )
