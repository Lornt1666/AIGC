import time
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from aigc_oidc_identity import (
    IdentityVerificationError,
    OIDCIdentityVerifier,
    OIDCTrustPolicy,
)


class FakeSigningKey:
    def __init__(self, key):
        self.key = key


class FakeJWKS:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, token):
        return FakeSigningKey(self.key)


class OIDCIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key()

    def setUp(self):
        self.consumed = set()
        self.revoked = set()
        self.policy = OIDCTrustPolicy(
            issuer="https://issuer.example.test",
            audience="urn:aigc:test",
            jwks_uri="https://issuer.example.test/.well-known/jwks.json",
            allowed_subjects=frozenset({"repo:Lornt1666/AIGC:ref:refs/heads/main"}),
            allowed_repositories=frozenset({"Lornt1666/AIGC"}),
            allowed_refs=frozenset({"refs/heads/main"}),
            allowed_workflows=frozenset({"AIGC CI"}),
            allowed_actions=frozenset({"governance:read", "evidence:verify"}),
            max_token_age_seconds=600,
        )
        self.verifier = OIDCIdentityVerifier(
            self.policy,
            jti_is_revoked=lambda jti: jti in self.revoked,
            consume_jti=self.consume,
            jwks_client=FakeJWKS(self.public_key),
        )

    def consume(self, jti, expiry):
        if jti in self.consumed:
            return False
        self.consumed.add(jti)
        return True

    def token(self, **overrides):
        now = int(time.time())
        claims = {
            "iss": self.policy.issuer,
            "sub": "repo:Lornt1666/AIGC:ref:refs/heads/main",
            "aud": self.policy.audience,
            "iat": now,
            "nbf": now - 1,
            "exp": now + 300,
            "jti": "token-unique-1",
            "repository": "Lornt1666/AIGC",
            "ref": "refs/heads/main",
            "workflow": "AIGC CI",
            "sha": "a" * 40,
        }
        claims.update(overrides)
        return jwt.encode(claims, self.private_key, algorithm="RS256", headers={"kid": "test-key"})

    def test_valid_signature_and_scoped_policy_authenticates(self):
        principal = self.verifier.authenticate(self.token(), required_actions={"governance:read"})
        self.assertEqual(principal.subject, "repo:Lornt1666/AIGC:ref:refs/heads/main")
        self.assertEqual(principal.repository, "Lornt1666/AIGC")
        self.assertEqual(principal.scopes, ("governance:read",))

    def test_tampered_signature_is_rejected(self):
        token = self.token()
        parts = token.split(".")
        parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
        with self.assertRaises(IdentityVerificationError):
            self.verifier.authenticate(".".join(parts), required_actions={"governance:read"})

    def test_wrong_audience_is_rejected(self):
        with self.assertRaises(IdentityVerificationError):
            self.verifier.authenticate(self.token(aud="urn:wrong"), required_actions={"governance:read"})

    def test_wrong_subject_is_rejected(self):
        with self.assertRaises(IdentityVerificationError):
            self.verifier.authenticate(self.token(sub="repo:attacker/other:ref:refs/heads/main"), required_actions={"governance:read"})

    def test_expired_token_is_rejected(self):
        now = int(time.time())
        with self.assertRaises(IdentityVerificationError):
            self.verifier.authenticate(
                self.token(iat=now - 900, nbf=now - 901, exp=now - 1),
                required_actions={"governance:read"},
            )

    def test_revoked_token_is_rejected(self):
        self.revoked.add("token-unique-1")
        with self.assertRaises(IdentityVerificationError):
            self.verifier.authenticate(self.token(), required_actions={"governance:read"})

    def test_replay_is_rejected(self):
        token = self.token()
        self.verifier.authenticate(token, required_actions={"governance:read"})
        with self.assertRaises(IdentityVerificationError):
            self.verifier.authenticate(token, required_actions={"governance:read"})

    def test_action_outside_policy_is_rejected(self):
        with self.assertRaises(IdentityVerificationError):
            self.verifier.authenticate(self.token(), required_actions={"deploy:production"})

    def test_wildcard_action_is_rejected(self):
        with self.assertRaises(IdentityVerificationError):
            self.verifier.authenticate(self.token(), required_actions={"*"})

    def test_missing_trust_subjects_rejected_at_configuration(self):
        with self.assertRaises(ValueError):
            OIDCTrustPolicy(issuer="https://issuer.example.test", audience="urn:test", jwks_uri="https://issuer.example.test/keys", allowed_subjects=frozenset())


if __name__ == "__main__":
    unittest.main()
