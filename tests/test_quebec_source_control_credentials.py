from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from scripts.validate_quebec_cloud_authorization import (
    AuthorizationError,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]


def _authorization_test_module():
    path = ROOT / "tests/test_quebec_cloud_authorization.py"
    spec = importlib.util.spec_from_file_location(
        "quebec_cloud_authorization_test_helpers",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("authorization test helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceControlCredentialTests(unittest.TestCase):
    def test_default_packet_blocks_legacy_credential_review(self) -> None:
        helpers = _authorization_test_module()
        packet = helpers.template()
        self.assertIs(
            packet["reviews"][
                "legacy_github_credentials_reviewed_and_revoked_or_proven_inactive"
            ],
            False,
        )

    def test_staging_fails_until_legacy_credentials_are_resolved(self) -> None:
        helpers = _authorization_test_module()
        packet = helpers.authorized()
        packet["reviews"][
            "legacy_github_credentials_reviewed_and_revoked_or_proven_inactive"
        ] = False
        with self.assertRaises(AuthorizationError):
            validate(
                packet,
                gate="staging",
                manifest=helpers.manifest(),
                now=helpers.TEST_NOW,
            )

    def test_validator_names_the_credential_review_gate(self) -> None:
        source = (
            ROOT / "scripts/validate_quebec_cloud_authorization.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "legacy_github_credentials_reviewed_and_revoked_or_proven_inactive",
            source,
        )


if __name__ == "__main__":
    unittest.main()
