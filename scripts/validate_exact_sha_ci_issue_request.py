from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

REQUIRED_CHECKS = {
    "contracts",
    "redaction",
    "procurement_smoke",
    "provider_discovery",
    "terraform_inert",
    "tests",
    "readiness",
}
ALLOWED_KEYS = {
    "schema_version",
    "request_id",
    "repository",
    "target_branch",
    "target_sha",
    "broker_revision",
    "requested_checks",
    "production_activation_authorized",
    "external_action_authorized",
}
ALLOWED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
LABEL = "exact-sha-ci-request"
COMPLETION_MARKER = "AIGC-EXACT-SHA-CI-COMPLETED"
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(access[_-]?token|refresh[_-]?token|client[_-]?secret|password)\s*[:=]"),
)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: object) -> str:
    return sha256(canonical(value)).hexdigest()


def extract_request(body: str) -> dict:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", body, flags=re.DOTALL | re.IGNORECASE)
    if len(blocks) != 1:
        raise ValueError("issue must contain exactly one fenced JSON request")
    try:
        value = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise ValueError("request JSON is malformed") from exc
    if not isinstance(value, dict):
        raise ValueError("request must be an object")
    return value


def validate_request(value: dict, expected_broker_revision: str) -> None:
    if set(value) != ALLOWED_KEYS:
        raise ValueError("request keys do not match the closed contract")
    if value["schema_version"] != "1.0.0":
        raise ValueError("unsupported schema version")
    if not re.fullmatch(r"CI-RECEIPT-[A-Z0-9-]{8,80}", value["request_id"]):
        raise ValueError("invalid request_id")
    if value["repository"] != "Lornt1666/AIGC" or value["target_branch"] != "main":
        raise ValueError("repository or branch mismatch")
    for field in ("target_sha", "broker_revision"):
        if not re.fullmatch(r"[a-f0-9]{40}", value[field]):
            raise ValueError(f"{field} must be a full lowercase SHA")
    if value["broker_revision"] != expected_broker_revision:
        raise ValueError("request broker revision mismatch")
    checks = value["requested_checks"]
    if not isinstance(checks, list) or set(checks) != REQUIRED_CHECKS or len(checks) != len(REQUIRED_CHECKS):
        raise ValueError("canonical checks are required exactly once")
    if value["production_activation_authorized"] is not False:
        raise ValueError("production activation is prohibited")
    if value["external_action_authorized"] is not False:
        raise ValueError("external action is prohibited")


def labels(issue: dict) -> set[str]:
    return {str(item.get("name")) for item in issue.get("labels", []) if isinstance(item, dict)}


def validate_issue(event: dict, issue: dict, comments: list[dict], expected_broker_revision: str) -> dict:
    if event.get("action") not in {"opened", "labeled"}:
        raise ValueError("unsupported issue event action")
    if issue.get("state") != "open":
        raise ValueError("request issue must be open")
    if LABEL not in labels(issue):
        raise ValueError("required request label is absent")
    if issue.get("author_association") not in ALLOWED_ASSOCIATIONS:
        raise ValueError("requester lacks repository authority")
    actor = event.get("sender") or {}
    author = issue.get("user") or {}
    if actor.get("id") != author.get("id") or actor.get("login") != author.get("login"):
        raise ValueError("event actor does not match issue author")
    body = str(issue.get("body") or "")
    if any(pattern.search(body) for pattern in SECRET_PATTERNS):
        raise ValueError("issue body appears to contain secret material")
    required_confirmations = (
        "[x] I confirm production activation is not authorized.",
        "[x] I confirm no external provider action is authorized.",
        "[x] I confirm this issue contains no credentials or secrets.",
    )
    lowered = body.lower()
    if any(item.lower() not in lowered for item in required_confirmations):
        raise ValueError("required authority confirmations are absent")
    request = extract_request(body)
    validate_request(request, expected_broker_revision)
    for comment in comments:
        text = str(comment.get("body") or "")
        if COMPLETION_MARKER in text and request["request_id"] in text:
            raise ValueError("issue request was already completed")
    binding = {
        "issue_number": int(issue["number"]),
        "issue_node_id": str(issue["node_id"]),
        "issue_created_at": str(issue["created_at"]),
        "issue_updated_at": str(issue["updated_at"]),
        "issue_body_sha256": sha256(body.encode()).hexdigest(),
        "actor_login": str(author["login"]),
        "actor_id": int(author["id"]),
        "request_id": request["request_id"],
        "target_sha": request["target_sha"],
        "broker_revision": request["broker_revision"],
        "request_sha256": digest(request),
    }
    binding["execution_binding_sha256"] = digest(binding)
    return {"request": request, "binding": binding}


def verify_unchanged(issue: dict, envelope: dict) -> None:
    binding = envelope["binding"]
    body = str(issue.get("body") or "")
    checks = {
        "issue_number": int(issue["number"]),
        "issue_node_id": str(issue["node_id"]),
        "issue_created_at": str(issue["created_at"]),
        "issue_body_sha256": sha256(body.encode()).hexdigest(),
        "actor_login": str((issue.get("user") or {})["login"]),
        "actor_id": int((issue.get("user") or {})["id"]),
    }
    for key, observed in checks.items():
        if binding.get(key) != observed:
            raise ValueError(f"issue changed after validation: {key}")
    if issue.get("state") != "open" or LABEL not in labels(issue):
        raise ValueError("issue state or label changed after validation")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--event", type=Path, required=True)
    validate.add_argument("--issue", type=Path, required=True)
    validate.add_argument("--comments", type=Path, required=True)
    validate.add_argument("--expected-broker-revision", required=True)
    validate.add_argument("--output", type=Path, required=True)
    recheck = subparsers.add_parser("recheck")
    recheck.add_argument("--issue", type=Path, required=True)
    recheck.add_argument("--envelope", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "validate":
        envelope = validate_issue(
            json.loads(args.event.read_text(encoding="utf-8")),
            json.loads(args.issue.read_text(encoding="utf-8")),
            json.loads(args.comments.read_text(encoding="utf-8")),
            args.expected_broker_revision,
        )
        args.output.write_bytes(canonical(envelope) + b"\n")
        print(json.dumps(envelope, sort_keys=True))
    else:
        verify_unchanged(
            json.loads(args.issue.read_text(encoding="utf-8")),
            json.loads(args.envelope.read_text(encoding="utf-8")),
        )


if __name__ == "__main__":
    main()
