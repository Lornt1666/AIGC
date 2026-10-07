from src.core.omega_worker_verification import Postcondition, PostconditionVerifier


def condition():
    return Postcondition(
        condition_id="pc-001",
        contract_id="contract-001",
        description="Required output exists and satisfies acceptance criteria.",
    )


def test_verifier_requires_evidence():
    try:
        PostconditionVerifier().verify(
            condition(),
            evidence="",
            check=lambda: True,
        )
    except ValueError:
        return
    raise AssertionError("missing evidence must fail closed")


def test_verifier_returns_verified_only_when_check_passes():
    result = PostconditionVerifier().verify(
        condition(),
        evidence="artifact://output-1",
        check=lambda: True,
    )

    assert result.status == "VERIFIED"


def test_verifier_does_not_promote_failed_check():
    result = PostconditionVerifier().verify(
        condition(),
        evidence="artifact://output-1",
        check=lambda: False,
    )

    assert result.status == "FAILED"
