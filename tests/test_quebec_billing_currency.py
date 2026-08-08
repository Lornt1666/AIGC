from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.validate_quebec_cloud_authorization import (
    AuthorizationError,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]


class BillingCurrencyTests(unittest.TestCase):
    def _template(self) -> dict:
        return json.loads(
            (
                ROOT / "config/quebec_staging_authorization.example.json"
            ).read_text(encoding="utf-8")
        )

    def test_plan_packet_requires_cad_billing_account_currency(self) -> None:
        payload = self._template()
        self.assertEqual(payload["billing_account_currency"], "CAD")
        result = validate(payload, gate="plan")
        self.assertEqual(result["billing_account_currency"], "CAD")

    def test_non_cad_billing_account_fails_before_any_gate(self) -> None:
        payload = self._template()
        payload["billing_account_currency"] = "USD"
        with self.assertRaises(AuthorizationError):
            validate(payload, gate="plan")

    def test_budget_currency_must_match_billing_account_currency(self) -> None:
        payload = self._template()
        payload["costs"]["currency"] = "USD"
        with self.assertRaises(AuthorizationError):
            validate(payload, gate="plan")

    def test_schema_requires_cad_billing_currency(self) -> None:
        schema = json.loads(
            (
                ROOT / "schemas/quebec_cloud_authorization.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertIn("billing_account_currency", schema["required"])
        self.assertEqual(
            schema["properties"]["billing_account_currency"]["const"],
            "CAD",
        )

    def test_terraform_rejects_non_cad_account_and_budget_uses_cad(self) -> None:
        currency = (
            ROOT / "infra/gcp/quebec/billing_currency.tf"
        ).read_text(encoding="utf-8")
        foundation = (
            ROOT / "infra/gcp/quebec/main.tf"
        ).read_text(encoding="utf-8")
        self.assertIn('var.billing_account_currency == "CAD"', currency)
        self.assertIn('currency_code = "CAD"', foundation)


if __name__ == "__main__":
    unittest.main()
