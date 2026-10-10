from __future__ import annotations

import hashlib
import hmac

from .models import OperatorIdentity


class GeminiAuthenticationError(RuntimeError):
    """Raised when an isolated Gemini surface cannot authenticate a caller."""


def stable_shared_principal_id(
    credential_binding_key: str,
    *,
    role: str,
) -> str:
    """Derive a label-independent identifier for one configured credential."""

    key = credential_binding_key.strip()
    if len(key) < 32:
        raise GeminiAuthenticationError(
            "Credential binding key must contain at least 32 characters"
        )
    if role not in {"operator", "judge", "runtime_admin"}:
        raise GeminiAuthenticationError("Unsupported Gemini principal role")
    return hmac.new(
        key.encode("utf-8"),
        f"aigc:gemini:shared-principal:v1:{role}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def attested_label_sha256(label: str, binding_key: str) -> str:
    """Hash an optional operator label without treating it as identity."""

    normalized = label.strip().lower() or "unlabeled"
    return hmac.new(
        binding_key.encode("utf-8"),
        f"aigc:gemini:attested-label:v1:{normalized}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def authenticate_shared_credential(
    *,
    provided_token: str,
    expected_token: str,
    credential_binding_key: str,
    role: str,
    attested_label: str = "",
) -> OperatorIdentity:
    """Authenticate a configured shared credential without logging its value."""

    if len(expected_token) < 32 or len(credential_binding_key) < 32:
        raise GeminiAuthenticationError(
            "Gemini application authentication is not configured"
        )
    if hmac.compare_digest(expected_token, credential_binding_key):
        raise GeminiAuthenticationError(
            "Authentication token and principal binding key must be distinct"
        )
    if not provided_token or not hmac.compare_digest(
        provided_token,
        expected_token,
    ):
        raise GeminiAuthenticationError("Gemini authentication failed")

    if role == "judge":
        auth_method = "shared_judge_token_header"
        assurance = "judge_credential_holder"
    elif role in {"operator", "runtime_admin"}:
        auth_method = "shared_token_header"
        assurance = "shared_credential_holder"
    else:
        raise GeminiAuthenticationError("Unsupported Gemini principal role")

    return OperatorIdentity(
        principal_id=stable_shared_principal_id(
            credential_binding_key,
            role=role,
        ),
        subject_sha256=attested_label_sha256(
            attested_label,
            credential_binding_key,
        ),
        role=role,
        auth_method=auth_method,
        identity_assurance=assurance,
    )
