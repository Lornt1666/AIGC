from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.cloud_advancement_loop import (  # noqa: E402
    CloudAdvancementStore,
    canonical_digest,
    execute_next,
    load_program,
    render_status_markdown,
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    program = load_program(root, args.config)
    store = CloudAdvancementStore(
        root,
        program,
        state_path=args.state_db,
    )

    if args.command == "status":
        status = store.status()
        if args.markdown:
            print(render_status_markdown(status), end="")
        else:
            print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0

    if args.command == "events":
        print(
            json.dumps(
                store.events(limit=args.limit),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "claim-next":
        result = store.claim_next(actor=args.actor)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "execute-next":
        result = execute_next(
            root,
            program,
            store,
            actor=args.actor,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "retry-action":
        result = store.retry_action(
            args.action_id,
            actor=args.actor,
            necessity_reason=args.necessity_reason,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "complete":
        evidence = {
            "evidence_refs": sorted(set(args.evidence)),
            "evidence_set_sha256": canonical_digest(
                sorted(set(args.evidence))
            ),
        }
        result = store.complete(
            args.run_id,
            actor=args.actor,
            evidence=evidence,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "block":
        evidence: dict[str, Any] = {
            "evidence_refs": sorted(set(args.evidence)),
        }
        fingerprint = args.blocker_fingerprint or canonical_digest(
            {
                "blocker_key": args.blocker_key,
                "reason": args.reason,
                "evidence_refs": evidence["evidence_refs"],
            }
        )
        result = store.block(
            args.run_id,
            actor=args.actor,
            blocker_key=args.blocker_key,
            blocker_fingerprint=fingerprint,
            reason=args.reason,
            evidence=evidence,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    raise ValueError(f"Unhandled command: {args.command}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the governed, dependency-ordered, non-repeating AIGC cloud "
            "advancement loop."
        )
    )
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/cloud_advancement_loop.json"),
    )
    parser.add_argument("--state-db", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--markdown", action="store_true")

    events_parser = subparsers.add_parser("events")
    events_parser.add_argument("--limit", type=int, default=100)

    claim_parser = subparsers.add_parser("claim-next")
    claim_parser.add_argument("--actor", required=True)

    execute_parser = subparsers.add_parser("execute-next")
    execute_parser.add_argument("--actor", required=True)

    retry_parser = subparsers.add_parser("retry-action")
    retry_parser.add_argument("--action-id", required=True)
    retry_parser.add_argument("--actor", required=True)
    retry_parser.add_argument("--necessity-reason", required=True)

    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument("--run-id", required=True)
    complete_parser.add_argument("--actor", required=True)
    complete_parser.add_argument("--evidence", nargs="+", required=True)

    block_parser = subparsers.add_parser("block")
    block_parser.add_argument("--run-id", required=True)
    block_parser.add_argument("--actor", required=True)
    block_parser.add_argument("--blocker-key", required=True)
    block_parser.add_argument("--blocker-fingerprint")
    block_parser.add_argument("--reason", required=True)
    block_parser.add_argument("--evidence", nargs="+", required=True)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
