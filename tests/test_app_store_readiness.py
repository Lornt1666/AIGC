from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "app_store"
SCHEMAS = ROOT / "schemas" / "app_store"
DOCS = ROOT / "docs" / "app_store"

ALLOWED_STATES = {
    "NOT_STARTED",
    "IMPLEMENTED",
    "LOCALLY_VALIDATED",
    "HOSTED_VALIDATED",
    "APPLE_VALIDATED",
    "BLOCKED",
}
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


class AppStoreReadinessTests(unittest.TestCase):
    def test_json_files_parse(self) -> None:
        for path in CONFIG.glob("*.json"):
            with self.subTest(path=path):
                load(path)
        for path in SCHEMAS.glob("*.json"):
            with self.subTest(path=path):
                load(path)

    def test_metadata_is_non_production_and_unresolved_fields_are_tbd(self) -> None:
        metadata = load(CONFIG / "app_store_metadata.example.json")
        self.assertIs(metadata["production_submission"], False)
        for key in (
            "app_name",
            "bundle_id",
            "privacy_policy_url",
            "support_url",
            "age_rating",
            "export_compliance",
            "price",
        ):
            self.assertEqual(metadata[key], "TBD")

    def test_data_practices_do_not_claim_tracking(self) -> None:
        practices = load(CONFIG / "data_practices.example.json")
        self.assertIs(practices["production_submission"], False)
        self.assertIs(practices["tracking"], False)
        self.assertTrue(
            all(item["tracking"] is False for item in practices["data_classes"])
        )

    def test_completion_ledger_vocabulary_and_authority(self) -> None:
        ledger = load(CONFIG / "completion_ledger.json")
        self.assertEqual(set(ledger["allowed_states"]), ALLOWED_STATES)
        self.assertTrue(
            all(state in ALLOWED_STATES for state in ledger["items"].values())
        )
        self.assertEqual(ledger["items"]["submission_authorization"], "BLOCKED")
        self.assertTrue(
            all(value is False for value in ledger["authority"].values())
        )

    def test_no_placeholder_is_apple_validated(self) -> None:
        ledger = load(CONFIG / "completion_ledger.json")
        self.assertNotIn("APPLE_VALIDATED", ledger["items"].values())
        metadata = load(CONFIG / "app_store_metadata.example.json")
        self.assertIn("TBD", metadata.values())

    def test_no_secret_like_values_in_app_store_examples(self) -> None:
        files = list(CONFIG.glob("*")) + list(SCHEMAS.glob("*"))
        for path in files:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in SECRET_PATTERNS:
                with self.subTest(path=path.name, pattern=pattern.pattern):
                    self.assertIsNone(pattern.search(text))

    def test_privacy_manifest_is_explicit_template_only(self) -> None:
        path = ROOT / "ios/RegenExcalibur/Resources/PrivacyInfo.xcprivacy.example"
        text = path.read_text(encoding="utf-8")
        self.assertIn("TEMPLATE_ONLY_NOT_FOR_SUBMISSION", text)
        self.assertIn("<key>NSPrivacyTracking</key>", text)
        self.assertIn("<false/>", text)

    def test_build_requirements_do_not_claim_xcode_success(self) -> None:
        text = (DOCS / "APPLE_BUILD_REQUIREMENTS.md").read_text(encoding="utf-8")
        self.assertIn("NOT A BUILD RECEIPT", text)
        self.assertIn("Xcode minimum for App Store Connect upload: 26", text)
        self.assertIn("iOS SDK minimum for App Store Connect upload: iOS 26", text)


if __name__ == "__main__":
    unittest.main()
