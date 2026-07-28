#!/usr/bin/env python3
"""Offline-by-default governed Gemini canary harness.

The default path performs no network call and retrieves no secret. Live mode is
blocked unless an exact, unexpired, one-time approval artifact satisfies every
fail-closed guard. This file is a policy harness, not an OS-level sandbox.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

FIXED_PROMPT = "Assess the supplied synthetic Canadian clean-energy opportunity. Identify assumptions, require human review, and perform no external business action."
ALLOWED_MODELS = {"gemini-2.5-flash", "gemini-2.5-pro"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def git_sha(root: Path) -> str | None:
    import subprocess
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=False, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and len(value) == 40 else None


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise ValueError("refusing symlink output")
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text); handle.flush(); os.fsync(handle.fileno()); temporary = Path(handle.name)
    os.replace(temporary, path)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("approval path must be a regular file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("approval must be an object")
    return value


def validate_approval(approval: dict[str, Any], *, sha: str, model: str, prompt_sha: str, idempotency_key: str) -> list[str]:
    errors: list[str] = []
    required = {
        "authorized": True,
        "action": "gemini_controlled_canary",
        "repository": "Lornt1666/AIGC",
        "git_sha": sha,
        "model": model,
        "prompt_sha256": prompt_sha,
        "idempotency_key_sha256": digest_text(idempotency_key),
        "maximum_model_calls": 1,
    }
    for key, expected in required.items():
        if approval.get(key) != expected:
            errors.append(f"approval field mismatch: {key}")
    if approval.get("revoked") is not False:
        errors.append("approval is revoked or revocation state is absent")
    if not isinstance(approval.get("approved_by"), str) or not approval["approved_by"].strip():
        errors.append("authenticated approver identity is absent")
    try:
        if parse_time(str(approval.get("expires_at"))) <= datetime.now(timezone.utc):
            errors.append("approval expired")
    except (TypeError, ValueError):
        errors.append("approval expiry invalid")
    for name in ("maximum_input_tokens", "maximum_output_tokens", "maximum_total_tokens"):
        value = approval.get(name)
        if not isinstance(value, int) or value <= 0:
            errors.append(f"invalid approval ceiling: {name}")
    budget = approval.get("maximum_cost_cad")
    if not isinstance(budget, (int, float)) or budget < 0:
        errors.append("invalid maximum_cost_cad")
    return errors


def reserve_idempotency(store: Path, key: str) -> bool:
    store.parent.mkdir(parents=True, exist_ok=True)
    digest = digest_text(key)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        descriptor = os.open(store.with_name(f"{store.name}.{digest}"), flags, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(utc_now() + "\n")
    return True


def default_provider(_: str, __: str, ___: int, ____: int) -> dict[str, Any]:
    raise RuntimeError("NOT_INTEGRATED_LIVE_EXECUTION_BLOCKED")


def execute(*, root: Path, output: Path, execute_live: bool, approval_path: Path | None, model: str | None, idempotency_key: str | None, stop_file: Path, idempotency_store: Path, provider: Callable[[str, str, int, int], dict[str, Any]] = default_provider) -> int:
    started = time.monotonic()
    sha = git_sha(root)
    prompt_sha = digest_text(FIXED_PROMPT)
    receipt: dict[str, Any] = {
        "schema_version": "1.0",
        "mode": "live" if execute_live else "dry_run",
        "started_at_utc": utc_now(),
        "repository": "Lornt1666/AIGC",
        "git_sha": sha,
        "prompt_sha256": prompt_sha,
        "model": model,
        "model_api_call_performed": False,
        "network_calls": 0,
        "external_business_action_performed": False,
        "tools_enabled": False,
        "arbitrary_url_context_enabled": False,
        "redactions_applied": True,
        "outcome": "DRY_RUN_COMPLETE",
        "limitations": ["Application-level policy harness; not proof of OS/container isolation.", "No cloud immutability is demonstrated by a local receipt."],
    }
    code = 0
    try:
        if not execute_live:
            return code
        if stop_file.exists():
            raise PermissionError("EMERGENCY_STOP_ACTIVE")
        if not sha:
            raise PermissionError("FULL_GIT_SHA_REQUIRED")
        if not model or model not in ALLOWED_MODELS:
            raise PermissionError("MODEL_NOT_ALLOWLISTED")
        if not approval_path or not idempotency_key:
            raise PermissionError("APPROVAL_AND_IDEMPOTENCY_REQUIRED")
        approval = load_json(approval_path)
        errors = validate_approval(approval, sha=sha, model=model, prompt_sha=prompt_sha, idempotency_key=idempotency_key)
        if errors:
            receipt["authorization_errors"] = errors
            raise PermissionError("APPROVAL_INVALID")
        if not reserve_idempotency(idempotency_store, idempotency_key):
            raise PermissionError("IDEMPOTENCY_REPLAY_BLOCKED")
        if stop_file.exists():
            raise PermissionError("EMERGENCY_STOP_ACTIVE")
        maximum_input = int(approval["maximum_input_tokens"])
        maximum_output = int(approval["maximum_output_tokens"])
        response = provider(FIXED_PROMPT, model, maximum_input, maximum_output)
        receipt["model_api_call_performed"] = True
        receipt["network_calls"] = 1
        receipt["provider"] = response.get("provider")
        receipt["model_version"] = response.get("model_version")
        receipt["response_id"] = response.get("response_id")
        receipt["usage"] = response.get("usage")
        receipt["output_sha256"] = digest_text(str(response.get("output", "")))
        receipt["outcome"] = "LIVE_CANARY_COMPLETE"
    except PermissionError as exc:
        receipt["outcome"] = str(exc)
        code = 2
    except RuntimeError as exc:
        receipt["outcome"] = str(exc)
        code = 3
    except Exception as exc:
        receipt["outcome"] = f"PROVIDER_OR_INTERNAL_FAILURE:{type(exc).__name__}"
        code = 70
    finally:
        receipt["completed_at_utc"] = utc_now()
        receipt["latency_ms"] = int((time.monotonic() - started) * 1000)
        atomic_write(output, receipt)
        print(json.dumps({"outcome": receipt["outcome"], "receipt": output.relative_to(root).as_posix() if output.is_relative_to(root) else str(output), "network_calls": receipt["network_calls"]}, sort_keys=True))
    return code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--idempotency-key")
    parser.add_argument("--output", type=Path, default=Path("artifacts/gemini-canary/dry-run-receipt.json"))
    parser.add_argument("--emergency-stop-file", type=Path, default=Path(".aigc/emergency-stop"))
    parser.add_argument("--idempotency-store", type=Path, default=Path(".aigc/idempotency"))
    args = parser.parse_args()
    root = Path.cwd().resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        output.resolve().relative_to(root)
    except ValueError:
        print("output must remain inside repository", file=sys.stderr); return 4
    return execute(root=root, output=output, execute_live=args.execute_live, approval_path=args.approval, model=args.model, idempotency_key=args.idempotency_key, stop_file=root / args.emergency_stop_file, idempotency_store=root / args.idempotency_store)


if __name__ == "__main__":
    raise SystemExit(main())
