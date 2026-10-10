from __future__ import annotations

from pathlib import Path
import os
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

FOCUSED_GEMINI_TESTS = [
    "tests/test_artifact_store_factory.py",
    "tests/test_durable_json_artifacts.py",
    "tests/test_production_artifact_store.py",
    "tests/test_controlled_gemini_canary.py",
    "tests/test_gcs_evidence_receipts.py",
    "tests/test_gemini_controls.py",
    "tests/test_gemini_image_allowlist.py",
    "tests/test_gemini_readiness.py",
    "tests/test_gemini_receipt_binding.py",
    "tests/test_gemini_staging_authorization.py",
    "tests/test_gemini_staging_deploy.py",
    "tests/test_gemini_surfaces.py",
    "tests/test_gemini_ui.py",
    "tests/test_gemini_workflow.py",
    "tests/test_judge_receipts.py",
    "tests/test_judge_store.py",
    "tests/test_publish_gemini_judge_receipt.py",
    "tests/test_secret_broker.py",
]


def main() -> int:
    return pytest.main(["-q", "-W", "error", *FOCUSED_GEMINI_TESTS])


if __name__ == "__main__":
    raise SystemExit(main())
