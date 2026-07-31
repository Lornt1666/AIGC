#!/usr/bin/env python3
"""Validate reference-only secret manifests without resolving secret values.

This validator checks metadata shape and rejects plaintext-bearing fields. It is
not a replacement for repository secret scanning, IAM review, rotation tests, or
runtime redaction tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DISCOVERY = (
    "governance/secret-references*.json",
    "governance/secret_references*.json",
    "config/secret-references*.json",
    "config/secret_references*.json",
    "secrets/manifest*.json",
)
PROHIBITED = {
    "value", "secret_value", "password", "passwd", "token", "api_key",
    "private_key", "client_secret", "credential", "credentials",
    "access_key", "key_material", "authorization", "cookie",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bgithub_pat_[0-9A-Za-z_]{20,}\b"),
    re.compile(r"\bgh[pousr]_[0-9A-Za-z]{20,}\b"),
    re.compile(r"\bsk-[0-9A-Za-z_-]{20,}\b"),
)
GCP_REF = re.compile(r"^projects/[A-Za-z0-9._:-]+/secrets/[A-Za-z0-9._-]+/versions/[A-Za-z0-9._-]+$")
REQUIRED = ("id", "provider", "purpose", "environment", "owner", "reference")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def unsafe_key(key: str) -> bool:
    normalized = normalize_key(key)
    return normalized in PROHIBITED or normalized.endswith("_value") or normalized.endswith("_password") or normalized.endswith("_api_key") or normalized.endswith("_private_key")


def walk(value: Any, path: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if unsafe_key(str(key)):
                findings.append({"code": "PROHIBITED_VALUE_FIELD", "path": child_path, "message": "plaintext-bearing field name is prohibited; value suppressed"})
                continue
            findings.extend(walk(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(walk(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in SECRET_PATTERNS):
            findings.append({"code": "SUSPECTED_SECRET_VALUE", "path": path, "message": "credential pattern detected; value suppressed"})
    return findings


def discover(root: Path) -> list[Path]:
    found: set[Path] = set()
    for pattern in DISCOVERY:
        found.update(path for path in root.glob(pattern) if path.is_file() and not path.is_symlink())
    return sorted(found)


def validate(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    data = path.read_bytes()
    result: dict[str, Any] = {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "status": "invalid", "findings": []}
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        result["findings"].append({"code": "MALFORMED_JSON", "path": "$", "message": "manifest must be valid UTF-8 JSON"})
        return result
    result["findings"].extend(walk(document))
    if not isinstance(document, dict) or document.get("schema_version") != "1.0" or not isinstance(document.get("secrets"), list):
        result["findings"].append({"code": "INVALID_SCHEMA", "path": "$", "message": "schema_version 1.0 and a secrets array are required"})
    else:
        for index, entry in enumerate(document["secrets"]):
            prefix = f"$.secrets[{index}]"
            if not isinstance(entry, dict):
                result["findings"].append({"code": "INVALID_ENTRY", "path": prefix, "message": "entry must be an object"})
                continue
            for field in REQUIRED:
                if not isinstance(entry.get(field), str) or not entry[field].strip():
                    result["findings"].append({"code": "MISSING_FIELD", "path": f"{prefix}.{field}", "message": "required non-empty string"})
            if entry.get("provider") == "gcp_secret_manager" and isinstance(entry.get("reference"), str) and not GCP_REF.fullmatch(entry["reference"]):
                result["findings"].append({"code": "INVALID_REFERENCE", "path": f"{prefix}.reference", "message": "expected a versioned Secret Manager resource reference"})
            consumers = entry.get("authorized_consumers")
            if consumers is not None and (not isinstance(consumers, list) or not all(isinstance(item, str) and item for item in consumers)):
                result["findings"].append({"code": "INVALID_CONSUMERS", "path": f"{prefix}.authorized_consumers", "message": "must be a list of non-empty identity strings"})
    result["entry_count"] = len(document.get("secrets", [])) if isinstance(document, dict) and isinstance(document.get("secrets"), list) else 0
    result["status"] = "valid" if not result["findings"] else "invalid"
    return result


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise ValueError("refusing symlink output")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        handle.flush(); os.fsync(handle.fileno()); temporary = Path(handle.name)
    os.replace(temporary, path)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--require-manifest", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("artifacts/secret-manifest-validation/receipt.json"))
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path.cwd().resolve()
    paths = [path.resolve() for path in args.paths]
    if args.discover:
        paths.extend(discover(root))
    paths = sorted(set(paths))
    if not paths and args.require_manifest:
        receipt = {"schema_version": "1.0", "generated_at_utc": utc_now(), "status": "invalid", "results": [], "errors": ["no manifest discovered"], "scope": "reference metadata only"}
        output = args.output if args.output.is_absolute() else root / args.output
        atomic_write(output, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        return 6
    results = []
    for path in paths:
        try:
            path.relative_to(root)
            if path.is_symlink() or not path.is_file():
                raise ValueError("path must be a regular repository file")
            results.append(validate(path, root))
        except (OSError, ValueError):
            results.append({"path": str(path), "status": "invalid", "findings": [{"code": "UNSAFE_OR_UNREADABLE_PATH", "path": "$", "message": "path rejected; content not read"}]})
    status = "valid" if all(item["status"] == "valid" for item in results) else "invalid"
    receipt = {"schema_version": "1.0", "generated_at_utc": utc_now(), "status": status, "results": results, "scope": "reference metadata only; no secret manager contacted and no secret value resolved"}
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        output.resolve().relative_to(root)
    except ValueError:
        print("output must remain inside repository", file=sys.stderr); return 5
    atomic_write(output, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "manifests": len(results), "receipt": output.relative_to(root).as_posix()}, sort_keys=True))
    return 0 if status == "valid" else 5


if __name__ == "__main__":
    raise SystemExit(main())
