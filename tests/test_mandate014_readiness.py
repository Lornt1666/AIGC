from __future__ import annotations

from fastapi.testclient import TestClient


def test_production_readiness_rejects_process_local_store(monkeypatch) -> None:
    """A live process-local store must never satisfy production readiness."""
    import src.webapp.app as webapp
    from src.webapp.command_center_store import MemoryCommandCenterStore

    monkeypatch.setenv("AIGC_ENV", "production")
    monkeypatch.setenv(
        "AIGC_COMMAND_CENTER_DATABASE_URL",
        "postgresql://configured-but-not-contacted.invalid/aigc",
    )
    monkeypatch.setattr(webapp, "_COMMAND_CENTER_STORE", MemoryCommandCenterStore())

    response = TestClient(webapp.app).get("/readyz")

    assert response.status_code == 503
    assert response.json()["detail"] == "Command-center dependencies are not ready."
