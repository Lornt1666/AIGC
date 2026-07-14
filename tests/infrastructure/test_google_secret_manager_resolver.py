from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.infrastructure.secrets import (
    GoogleSecretManagerResolver,
    SecretManagerPolicyError,
    parse_secret_reference,
)


@dataclass(frozen=True)
class FakePayload:
    data: bytes


@dataclass(frozen=True)
class FakeResponse:
    payload: FakePayload
    name: str


class FakeClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, str]] = []

    def access_secret_version(self, *, request: dict[str, str]) -> FakeResponse:
        self.requests.append(dict(request))
        return FakeResponse(
            payload=FakePayload(b"offline-secret-material"),
            name=request["name"],
        )


def test_reference_parser_is_strict() -> None:
    reference = parse_secret_reference(
        "gcp_secret://approved-project/aigc-github-app/latest"
    )

    assert reference.project_id == "approved-project"
    assert reference.secret_id == "aigc-github-app"
    assert reference.version == "latest"
    assert reference.resource_name == (
        "projects/approved-project/secrets/aigc-github-app/versions/latest"
    )

    minimum = parse_secret_reference("gcp_secret://abc123/value/latest")
    maximum_project_id = "a" + ("b" * 28) + "1"
    maximum = parse_secret_reference(
        f"gcp_secret://{maximum_project_id}/value/latest"
    )
    assert minimum.project_id == "abc123"
    assert maximum.project_id == maximum_project_id

    for value in (
        "https://example.invalid/secret",
        "gcp_secret://short/value/latest",
        "gcp_secret://approved-project/value",
        "gcp_secret://approved_project/value/latest",
        "gcp_secret://approved-project-/value/latest",
        f"gcp_secret://{'a' * 31}/value/latest",
    ):
        with pytest.raises(SecretManagerPolicyError):
            parse_secret_reference(value)


def test_unauthorized_placeholder_and_cross_project_access_fail_before_client() -> None:
    client = FakeClient()

    unauthorized = GoogleSecretManagerResolver(
        expected_project_id="approved-project",
        access_authorized=False,
        client=client,
    )
    placeholder = GoogleSecretManagerResolver(
        expected_project_id=None,
        access_authorized=True,
        client=client,
    )
    cross_project = GoogleSecretManagerResolver(
        expected_project_id="approved-project",
        access_authorized=True,
        client=client,
    )

    with pytest.raises(SecretManagerPolicyError, match="not authorized"):
        unauthorized.access(
            "gcp_secret://approved-project/aigc-github-app/latest"
        )
    with pytest.raises(SecretManagerPolicyError, match="unresolved"):
        placeholder.access(
            "gcp_secret://TBD_PROJECT/aigc-github-app/latest"
        )
    with pytest.raises(SecretManagerPolicyError, match="not allowlisted"):
        cross_project.access(
            "gcp_secret://other-project/aigc-github-app/latest"
        )

    assert client.requests == []


def test_authorized_fake_access_returns_redacted_receipt_and_zeroizable_material() -> None:
    client = FakeClient()
    resolver = GoogleSecretManagerResolver(
        expected_project_id="approved-project",
        access_authorized=True,
        client=client,
    )

    resolved = resolver.access(
        "gcp_secret://approved-project/aigc-github-app/1"
    )
    material = resolved.bytes()
    receipt = resolved.receipt.to_dict()

    assert material == b"offline-secret-material"
    assert receipt["reference"] == (
        "gcp_secret://approved-project/aigc-github-app/1"
    )
    assert receipt["raw_value_logged"] is False
    assert receipt["raw_value_persisted"] is False
    assert receipt["external_action_performed"] is False
    assert "offline-secret-material" not in str(receipt)
    assert client.requests == [
        {
            "name": (
                "projects/approved-project/secrets/"
                "aigc-github-app/versions/1"
            )
        }
    ]

    resolved.close()
    with pytest.raises(SecretManagerPolicyError, match="closed"):
        resolved.bytes()
