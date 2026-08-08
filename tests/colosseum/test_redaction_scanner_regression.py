from src.security.redaction_scanner import RedactionScanner


def test_task_identifier_is_not_misclassified_as_provider_key() -> None:
    scanner = RedactionScanner()
    findings = scanner.scan_text(
        'task_id="task-validation"',
        path="synthetic_fixture.py",
    )
    assert findings == []


def test_real_provider_key_prefix_remains_rejected_and_redacted() -> None:
    scanner = RedactionScanner()
    key_like_value = "s" + "k-" + ("A" * 24)
    findings = scanner.scan_text(
        f'api_key="{key_like_value}"',
        path="unsafe_fixture.py",
    )
    assert findings
    assert any("sk-" in finding.pattern for finding in findings)
    assert all(key_like_value not in finding.redacted_preview for finding in findings)
