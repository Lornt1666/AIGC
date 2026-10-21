"""Verify a real GitHub Actions OIDC token against AIGC's narrow CI trust policy.

This verifier is intentionally scoped to the trusted main-branch evidence-attestation
job. It emits no token or unbounded claims. In-memory jti consumption is suitable only
for this single-process CI proof; production services must use independent durable replay
and revocation storage.
"""
from __future__ import annotations

import json
import os
import time
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
from urllib.request import Request, urlopen

from aigc_oidc_identity import OIDCIdentityVerifier, OIDCTrustPolicy, IdentityVerificationError

REPOSITORY = "Lornt1666/AIGC"
REPOSITORY_ID = "1287333065"
WORKFLOW_NAME = "AIGC CI"
WORKFLOW_REF = "Lornt1666/AIGC/.github/workflows/aigc-ci.yml@refs/heads/main"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
OIDC_AUDIENCE = "urn:aigc:release-evidence:verify"


def validate_bound_claims(claims: dict, *, expected_sha: str, expected_run_id: str,
                          expected_run_attempt: str) -> None:
    expected = {
        "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID,
        "ref": "refs/heads/main",
        "workflow": WORKFLOW_NAME,
        "workflow_ref": WORKFLOW_REF,
        "workflow_sha": expected_sha,
        "sha": expected_sha,
        "event_name": "push",
        "run_id": expected_run_id,
        "run_attempt": expected_run_attempt,
    }
    for claim, value in expected.items():
        actual = claims.get(claim)
        if str(actual) != value:
            raise IdentityVerificationError("oidc_claim_mismatch:" + claim)


def request_oidc_token() -> str:
    endpoint = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or parsed.hostname != "token.actions.githubusercontent.com":
        raise IdentityVerificationError("oidc_request_endpoint_untrusted")
    if not request_token:
        raise IdentityVerificationError("oidc_request_token_missing")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["audience"] = OIDC_AUDIENCE
    url = urlunparse(parsed._replace(query=urlencode(query)))
    request = Request(url, headers={"Authorization": "Bearer " + request_token,
                                    "Accept": "application/json"})
    with urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise IdentityVerificationError("oidc_token_endpoint_failed")
        body = json.loads(response.read(1024 * 1024).decode("utf-8"))
    token = body.get("value") if isinstance(body, dict) else None
    if not isinstance(token, str) or not token:
        raise IdentityVerificationError("oidc_token_response_invalid")
    return token


def main() -> int:
    expected_sha = os.environ.get("GITHUB_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if len(expected_sha) != 40 or any(c not in "0123456789abcdef" for c in expected_sha):
        raise SystemExit("BLOCK: invalid expected commit SHA")
    if not run_id.isdigit() or not run_attempt.isdigit():
        raise SystemExit("BLOCK: missing workflow run identity")

    policy = OIDCTrustPolicy(
        issuer=OIDC_ISSUER,
        audience=OIDC_AUDIENCE,
        jwks_uri=OIDC_ISSUER + "/.well-known/jwks",
        allowed_subjects=frozenset({"repo:" + REPOSITORY + ":ref:refs/heads/main"}),
        allowed_repositories=frozenset({REPOSITORY}),
        allowed_refs=frozenset({"refs/heads/main"}),
        allowed_workflows=frozenset({WORKFLOW_NAME}),
        allowed_actions=frozenset({"evidence:attest"}),
        max_token_age_seconds=600,
        leeway_seconds=30,
    )
    consumed: set[str] = set()

    def consume(jti: str, expiry: int) -> bool:
        if expiry <= int(time.time()) or jti in consumed:
            return False
        consumed.add(jti)
        return True

    verifier = OIDCIdentityVerifier(
        policy,
        jti_is_revoked=lambda jti: False,
        consume_jti=consume,
    )
    token = request_oidc_token()
    try:
        principal = verifier.authenticate(token, required_actions={"evidence:attest"})
        # Verify the signed token's complete workflow context in addition to the
        # identity verifier's issuer/audience/subject/repository/ref/workflow checks.
        import jwt
        claims = jwt.decode(token, options={"verify_signature": False, "verify_exp": False,
                                             "verify_aud": False, "verify_iss": False})
        validate_bound_claims(claims, expected_sha=expected_sha,
                              expected_run_id=run_id, expected_run_attempt=run_attempt)
    except IdentityVerificationError as exc:
        raise SystemExit("BLOCK: " + str(exc)) from exc

    # The unverified decode above is only used to inspect claims after the same token
    # has already passed signature/JWKS/issuer/audience/time validation in authenticate().
    print(json.dumps({
        "schema_version": "aigc-github-oidc-evidence/1.0",
        "status": "VERIFIED",
        "repository": principal.repository,
        "subject": principal.subject,
        "issuer": principal.issuer,
        "audience": principal.audience,
        "ref": principal.ref,
        "workflow": principal.workflow,
        "source_sha": expected_sha,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "actions": list(principal.scopes),
        "token_emitted": False,
        "production_authority": False,
        "release_authority": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
