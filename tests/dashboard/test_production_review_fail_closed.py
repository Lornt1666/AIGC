from __future__ import annotations

from src.dashboard.operator_cockpit_app import _filesystem_review_allowed


def test_dashboard_filesystem_review_is_disabled_in_production(monkeypatch):
    monkeypatch.setenv("AIGC_ENV", "production")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert _filesystem_review_allowed() is False


def test_dashboard_filesystem_review_is_disabled_in_prod_alias(monkeypatch):
    monkeypatch.setenv("AIGC_ENV", "prod")
    assert _filesystem_review_allowed() is False


def test_dashboard_filesystem_review_remains_available_in_development(monkeypatch):
    monkeypatch.setenv("AIGC_ENV", "development")
    assert _filesystem_review_allowed() is True


def test_dashboard_environment_fallback_is_respected(monkeypatch):
    monkeypatch.delenv("AIGC_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert _filesystem_review_allowed() is False

def test_production_environment_cannot_be_overridden_by_development_alias(monkeypatch):
    monkeypatch.setenv("AIGC_ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert _filesystem_review_allowed() is False


def test_prod_environment_alias_cannot_be_overridden_by_development(monkeypatch):
    monkeypatch.setenv("AIGC_ENV", "prod")
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert _filesystem_review_allowed() is False
