from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / "infra/gcp/quebec"


def tf_text(name: str) -> str:
    return (TF / name).read_text(encoding="utf-8")


def assert_balanced_hcl(text: str) -> None:
    stack: list[str] = []
    pairs = {"}": "{", "]": "[", ")": "("}
    quote: str | None = None
    escaped = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch == "#":
            in_line_comment = True
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch in {'"', "'"}:
            quote = ch
        elif ch in "{[(":
            stack.append(ch)
        elif ch in "}])":
            if not stack or stack.pop() != pairs[ch]:
                raise AssertionError(f"unbalanced HCL near {ch!r}")
        i += 1
    if quote or in_block_comment or stack:
        raise AssertionError(
            "unterminated string/comment or unbalanced delimiters"
        )


class FoundationStaticTests(unittest.TestCase):
    def test_all_terraform_files_have_balanced_syntax(self) -> None:
        for path in TF.glob("*.tf"):
            with self.subTest(path=path.name):
                assert_balanced_hcl(path.read_text(encoding="utf-8"))

    def test_region_is_locked_to_montreal(self) -> None:
        variables = tf_text("variables.tf")
        self.assertIn(
            'var.region == "northamerica-northeast1"',
            variables,
        )
        self.assertNotIn(
            'northamerica-northeast2"\n  validation',
            variables,
        )

    def test_no_service_account_key_resource_exists(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in TF.glob("*.tf")
        )
        self.assertNotIn('resource "google_service_account_key"', combined)
        self.assertNotIn("private_key", combined.lower())

    def test_no_public_iam_member_is_created(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in TF.glob("*.tf")
        )
        self.assertNotIn('member = "allUsers"', combined)
        self.assertNotIn('member = "allAuthenticatedUsers"', combined)
        self.assertIn('member != "allUsers"', combined)

    def test_cloud_run_is_separated_from_foundation_authority(self) -> None:
        cloud_run = tf_text("main.tf")
        self.assertNotIn('resource "google_cloud_run', cloud_run)
        self.assertIn("intentionally not created", cloud_run)
        self.assertIn("live_model_call_authorized == false", cloud_run)

    def test_cloud_sql_is_private_regional_ha(self) -> None:
        sql = tf_text("main.tf")
        self.assertIn('availability_type = "REGIONAL"', sql)
        self.assertIn("ipv4_enabled", sql)
        self.assertIn("false", sql)
        self.assertIn("private_network", sql)
        self.assertIn("point_in_time_recovery_enabled = true", sql)
        self.assertIn("location", sql)

    def test_storage_is_regional_private_versioned_and_retained(self) -> None:
        storage = tf_text("main.tf")
        for required in (
            "location                    = upper(var.region)",
            "uniform_bucket_level_access = true",
            'public_access_prevention    = "enforced"',
            "enabled = true",
            "retention_policy",
        ):
            self.assertIn(required, storage)

    def test_artifact_registry_uses_immutable_tags(self) -> None:
        artifact = tf_text("main.tf")
        self.assertIn("immutable_tags = true", artifact)
        self.assertIn("location      = var.region", artifact)

    def test_secret_references_require_numeric_montreal_versions(self) -> None:
        variables = tf_text("variables.tf")
        secrets = tf_text("main.tf")
        self.assertIn("locations/northamerica-northeast1", variables)
        self.assertIn("versions/[1-9][0-9]*", variables)
        self.assertIn("/versions/latest", secrets)
        self.assertIn("!endswith", secrets)

    def test_budget_is_cad_and_bounded(self) -> None:
        budgets = tf_text("main.tf")
        variables = tf_text("variables.tf")
        self.assertIn('currency_code = "CAD"', budgets)
        self.assertIn("var.monthly_budget_cad <= 200", variables)
        self.assertIn("0.50", budgets)
        self.assertIn("1.00", budgets)

    def test_every_resource_is_default_deny_gated(self) -> None:
        main = tf_text("main.tf")
        resource_blocks = re.findall(
            r'resource\s+"[^"]+"\s+"[^"]+"\s*\{'
            r'(.*?)(?=\nresource\s+"|\ncheck\s+"|\Z)',
            main,
            flags=re.DOTALL,
        )
        self.assertGreater(len(resource_blocks), 10)
        for block in resource_blocks:
            self.assertTrue(
                "local.create_resources" in block,
                "resource lacks default-deny gating",
            )

    def test_docs_preserve_truth_boundary(self) -> None:
        document = (
            ROOT / "docs/cloud/QUEBEC_CLOUD_FOUNDATION.md"
        ).read_text(encoding="utf-8")
        self.assertIn("global hyperscale provider", document)
        self.assertIn("Codex/ChatGPT processing", document)
        self.assertIn("Sanitized non-personal", document)
        self.assertIn("Toronto copy not authorized", document)


if __name__ == "__main__":
    unittest.main()
