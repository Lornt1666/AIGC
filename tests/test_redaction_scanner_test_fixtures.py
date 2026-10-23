from __future__ import annotations

from src.security.redaction_scanner import RedactionScanner


def test_explicit_for_tests_fixtures_are_ignored_only_under_tests() -> None:
    scanner = RedactionScanner()
    keyword_fixture = (
        'provided_token="operator-value-for-tests-1234567890"'
    )
    header_fixture = (
        '"X-AIGC-Operator-Token": '
        '"operator-value-for-tests-1234567890"'
    )

    assert scanner.scan_text(keyword_fixture, path="tests/test_fixture.py") == []
    assert scanner.scan_text(header_fixture, path="tests/test_fixture.py") == []
    assert scanner.scan_text(keyword_fixture, path="src/runtime.py")
    assert scanner.scan_text(header_fixture, path="src/runtime.py")


def test_real_prefixed_secret_is_still_detected_under_tests() -> None:
    scanner = RedactionScanner()
    real_value = "".join(("ghp_", "a" * 24))

    findings = scanner.scan_text(
        f'provided_token="{real_value}"',
        path="tests/test_fixture.py",
    )

    assert findings
    assert any(finding.severity == "high" for finding in findings)


def test_ci_workflow_test_only_values_are_ignored_but_secret_like_values_are_not() -> None:
    scanner = RedactionScanner()
    workflow_path = ".github/workflows/aigc-ci.yml"
    fixture_value = "test_" + "only_ci_password_fixture_0123456789abcdef"
    assignment_prefix = "POSTGRES_" + "PASSWORD: "

    assert scanner.scan_text(assignment_prefix + fixture_value, path=workflow_path) == []

    secret_value = "".join(("aB3!", "xY7@", "mN9#", "pQ2$", "rS5%"))
    findings = scanner.scan_text(assignment_prefix + secret_value, path=workflow_path)
    assert findings
