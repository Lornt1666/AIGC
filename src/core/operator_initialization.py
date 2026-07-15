from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable

from src.core.operator_cockpit import (
    CommandResult,
    GovernedCommand,
    build_aigc_command,
    run_command_sequence,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_ROOT = Path("reports/artifacts/operator_initialization")

INITIALIZATION_BOUNDARY = [
    "local database initialization only",
    "contract, health, readiness, and cockpit validation only",
    "work-acquisition preparation is read-only and internal",
    "provider discovery is mock-only and no-network",
    "no package installation, credential use, provider mutation, Terraform apply, job submission, messaging, contract acceptance, interview scheduling, deployment, or delivery",
]


@dataclass(frozen=True)
class InitializationReceipt:
    receipt_id: str
    exact_revision: str
    created_at: str
    status: str
    steps: list[dict[str, Any]]
    boundary: list[str]
    operator_review_required: bool
    external_action_performed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def exact_revision(root: Path = PROJECT_ROOT) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip()
    if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
        raise ValueError("AIGC initialization requires an exact 40-character Git revision.")
    return revision


def build_initialization_commands(root: Path = PROJECT_ROOT) -> list[GovernedCommand]:
    revision = exact_revision(root)
    mock_output = root / "reports" / "artifacts" / "provider_discovery_simulation" / "operator_initialize"
    return [
        GovernedCommand(
            "Initialize local state database",
            build_aigc_command(root, "init-db"),
            "local_sqlite_only",
        ),
        GovernedCommand(
            "Validate repository contracts",
            build_aigc_command(root, "validate"),
            "schema_contract_validation",
        ),
        GovernedCommand(
            "Evaluate local program health",
            build_aigc_command(root, "health", "--write"),
            "local_health_evidence",
        ),
        GovernedCommand(
            "Evaluate structural readiness",
            build_aigc_command(root, "readiness"),
            "structural_not_operational_proof",
        ),
        GovernedCommand(
            "Prepare read-only work-acquisition packet",
            build_aigc_command(root, "run", "work-acquisition"),
            "read_only_search_and_drafting_only",
        ),
        GovernedCommand(
            "Run cockpit smoke test",
            build_aigc_command(root, "run", "cockpit-smoke"),
            "local_cockpit_validation",
        ),
        GovernedCommand(
            "Run mock-only provider discovery",
            [
                sys.executable,
                str(root / "scripts" / "run_provider_discovery_mock.py"),
                "--repository-revision",
                revision,
                "--output-dir",
                str(mock_output),
            ],
            "mock_only_no_network",
        ),
    ]


def run_operator_initialization(
    root: Path = PROJECT_ROOT,
    *,
    artifact_root: Path | None = None,
    stop_on_failure: bool = True,
) -> InitializationReceipt:
    root = root.resolve()
    revision = exact_revision(root)
    commands = build_initialization_commands(root)
    results = run_command_sequence(commands, root, stop_on_failure=stop_on_failure)
    status = "READY_FOR_OPERATOR_REVIEW" if len(results) == len(commands) and all(item.ok for item in results) else "INITIALIZATION_BLOCKED"
    created_at = datetime.now(timezone.utc).isoformat()
    material = "|".join(
        [revision, created_at, status]
        + [f"{item.label}:{item.returncode}" for item in results]
    )
    receipt = InitializationReceipt(
        receipt_id="AIGC-INIT-" + sha256(material.encode("utf-8")).hexdigest()[:24].upper(),
        exact_revision=revision,
        created_at=created_at,
        status=status,
        steps=[
            {
                "label": item.label,
                "command": item.command,
                "returncode": item.returncode,
                "ok": item.ok,
                "stdout_tail": item.stdout[-2000:],
                "stderr_tail": item.stderr[-2000:],
                "external_action_performed": False,
            }
            for item in results
        ],
        boundary=list(INITIALIZATION_BOUNDARY),
        operator_review_required=True,
        external_action_performed=False,
    )
    output_root = root / (artifact_root or DEFAULT_ARTIFACT_ROOT) / receipt.receipt_id
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "initialization_receipt.json").write_text(
        json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def results_are_internal(results: Iterable[CommandResult]) -> bool:
    forbidden = (
        "terraform apply",
        "auto_apply",
        "auto_submit",
        "auto_message",
        "send email",
        "schedule interview",
        "accept contract",
    )
    text = "\n".join(" ".join(item.command).lower() for item in results)
    return not any(marker in text for marker in forbidden)
