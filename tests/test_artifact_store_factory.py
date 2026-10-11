from __future__ import annotations

import pytest

from src.core.artifact_store_factory import artifact_store_from_env
from src.core.production_artifact_store import ArtifactUnavailable


def test_factory_fails_closed_without_shared_storage_configuration(monkeypatch):
    for key in (
        "AIGC_ARTIFACT_BUCKET",
        "AIGC_ARTIFACT_DATABASE_URL",
        "AIGC_COMMAND_CENTER_DATABASE_URL",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "AIGC_COMMAND_CENTER_DB_SSLROOTCERT",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ArtifactUnavailable, match="requires AIGC_ARTIFACT_BUCKET"):
        artifact_store_from_env()


def test_factory_rejects_non_verifying_database_tls(monkeypatch, tmp_path):
    cert = tmp_path / "ca.pem"
    cert.write_text("test-ca", encoding="utf-8")
    monkeypatch.setenv("AIGC_ARTIFACT_BUCKET", "private-test-bucket")
    monkeypatch.setenv("AIGC_ARTIFACT_DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("AWS_REGION", "ca-central-1")
    monkeypatch.setenv("AIGC_COMMAND_CENTER_DB_SSLMODE", "require")
    monkeypatch.setenv("AIGC_COMMAND_CENTER_DB_SSLROOTCERT", str(cert))
    with pytest.raises(ArtifactUnavailable, match="sslmode=verify-full"):
        artifact_store_from_env()


def test_factory_requires_existing_database_ca_bundle(monkeypatch):
    monkeypatch.setenv("AIGC_ARTIFACT_BUCKET", "private-test-bucket")
    monkeypatch.setenv("AIGC_ARTIFACT_DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("AWS_REGION", "ca-central-1")
    monkeypatch.setenv("AIGC_COMMAND_CENTER_DB_SSLMODE", "verify-full")
    monkeypatch.setenv("AIGC_COMMAND_CENTER_DB_SSLROOTCERT", "/not/a/real/ca.pem")
    with pytest.raises(ArtifactUnavailable, match="readable database CA bundle"):
        artifact_store_from_env()
