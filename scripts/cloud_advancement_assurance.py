from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from jsonschema.exceptions import SchemaError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.cloud_advancement_assurance import (  # noqa: E402
    CloudAdvancementAssuranceStore,
    load_assurance_config,
)
from src.core.cloud_advancement_loop import (  # noqa: E402
    CloudAdvancementError,
    load_program,
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return _execute(args)
    except (
        CloudAdvancementError,
        json.JSONDecodeError,
        SchemaError,
        sqlite3.Error,
        UnicodeError,
        OSError,
    ) as exc:
        print(
            json.dumps(
                {
                    "status": "verification_error",
                    "error": str(exc),
                    "external_action_performed": False,
                },
                indent=2,
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 10


def _execute(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    assurance = load_assurance_config(root)
    program = load_program(
        root,
        Path(str(assurance["program_config"])),
    )
    store = CloudAdvancementAssuranceStore(
        root,
        program,
        assurance,
        initialize=args.command in {"remember", "measure"},
    )

    if args.command == "remember":
        result = store.remember(
            key=args.key,
            value=_parse_json_value(args.value_json),
            scope=args.scope,
            actor=args.actor,
            source_refs=args.source_ref,
            source_sha256=args.source_sha256,
            idempotency_key=args.idempotency_key,
            derivation_type=args.derivation_type,
            confidence=args.confidence,
            salience=args.salience,
            ttl_hours=args.ttl_hours,
            action_id=args.action_id,
            run_id=args.run_id,
        )
        return _print_result(result)

    if args.command == "recall":
        result = {
            "status": "recalled",
            "entries": store.recall(
                query=args.query,
                scope=args.scope,
                action_id=args.action_id,
                run_id=args.run_id,
                limit=args.limit,
            ),
            "external_action_performed": False,
        }
        return _print_result(result)

    if args.command == "measure":
        result = store.record_metric(
            metric_id=args.metric_id,
            idempotency_key=args.idempotency_key,
            actor=args.actor,
        )
        return _print_result(result)

    if args.command == "summary":
        result = {
            "working_memory": store.memory_summary(),
            "quantitative_accuracy": store.metric_summary(),
            "external_action_performed": False,
        }
        return _print_result(result)

    if args.command == "verify":
        receipt = store.verify(anchor_receipt=args.anchor_receipt)
        _print_result(receipt)
        return _verification_exit_code(receipt)

    if args.command == "checkpoint":
        receipt = store.verify(anchor_receipt=args.anchor_receipt)
        exit_code = _verification_exit_code(receipt)
        if exit_code:
            _print_result(receipt)
            return exit_code
        written, finalized = store.write_verification_receipt(
            receipt,
            args.output,
        )
        return _print_result(
            {
                "receipt": finalized,
                "written_to": str(
                    written.relative_to(root)
                ).replace("\\", "/"),
            }
        )

    raise ValueError(f"Unhandled command: {args.command}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Operate the quantitative, working-memory, performance, and "
            "verification assurance plane for the AIGC cloud loop."
        )
    )
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    remember = subparsers.add_parser("remember")
    remember.add_argument("--key", required=True)
    remember.add_argument(
        "--scope",
        required=True,
        choices=["program", "action", "run"],
    )
    remember.add_argument("--value-json", required=True)
    remember.add_argument("--actor", required=True)
    remember.add_argument(
        "--source-ref",
        action="append",
        required=True,
    )
    remember.add_argument(
        "--source-sha256",
        action="append",
        required=True,
    )
    remember.add_argument("--idempotency-key", required=True)
    remember.add_argument(
        "--derivation-type",
        required=True,
        choices=["direct_observation", "deterministic_derivation"],
    )
    remember.add_argument("--confidence", default="1")
    remember.add_argument("--salience", default="0.5")
    remember.add_argument("--ttl-hours", type=int)
    remember.add_argument("--action-id", default="")
    remember.add_argument("--run-id", default="")

    recall = subparsers.add_parser("recall")
    recall.add_argument("--query", default="")
    recall.add_argument(
        "--scope",
        required=True,
        choices=["program", "action", "run"],
    )
    recall.add_argument("--action-id", default="")
    recall.add_argument("--run-id", default="")
    recall.add_argument("--limit", type=int)

    measure = subparsers.add_parser("measure")
    measure.add_argument("--metric-id", required=True)
    measure.add_argument("--idempotency-key", required=True)
    measure.add_argument("--actor", required=True)

    subparsers.add_parser("summary")

    verify = subparsers.add_parser("verify")
    verify.add_argument("--anchor-receipt", type=Path)
    checkpoint = subparsers.add_parser("checkpoint")
    checkpoint.add_argument("--anchor-receipt", type=Path)
    checkpoint.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def _parse_json_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise CloudAdvancementError(
            "Working-memory value must be valid JSON."
        ) from exc


def _print_result(result: Any) -> int:
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _verification_exit_code(receipt: dict[str, Any]) -> int:
    if receipt["assurance_passed"]:
        return 0
    structural_checks = {
        "program_and_assurance_config_valid",
        "sqlite_integrity_valid",
        "foreign_keys_valid",
        "append_only_controls_valid",
        "event_chain_valid",
        "program_binding_valid",
        "assurance_binding_valid",
        "loop_history_valid",
        "required_artifacts_present",
        "secrets_absent",
    }
    if any(not receipt["checks"][name] for name in structural_checks):
        return 10
    return 11


if __name__ == "__main__":
    raise SystemExit(main())
