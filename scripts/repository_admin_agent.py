#!/usr/bin/env python3
"""Read-only repository governance assessment for AIGC.

This tool does not mutate GitHub settings, approve releases, merge PRs, create tags,
or deploy. It emits a conservative BLOCK report whenever settings cannot be read or
required protections cannot be positively verified.

Usage:
  GITHUB_TOKEN=... python scripts/repository_admin_agent.py
  GITHUB_TOKEN=... python scripts/repository_admin_agent.py --repo Lornt1666/AIGC

Use a fine-grained token with read-only repository metadata and administration
permissions. Never provide this tool a token with write permissions: it does not
need them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

API_ROOT = "https://api.github.com"
DEFAULT_REPO = "Lornt1666/AIGC"
REQUIRED_TAG_PATTERN_HINT = "v*"


class GitHubReadError(RuntimeError):
    def __init__(self, status: int, endpoint: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.endpoint = endpoint


def github_get(repo: str, endpoint: str, token: str | None) -> Any:
    request = urllib.request.Request(
        f"{API_ROOT}/repos/{repo}/{endpoint.lstrip('/')}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": f"Bearer {token}"} if token else {}),
            "User-Agent": "AIGC-Repository-Administrator-Agent/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(1024).decode("utf-8", errors="replace")
        raise GitHubReadError(exc.code, endpoint, detail or exc.reason) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read GitHub endpoint {endpoint}: {exc}") from exc


def error_state(exc: GitHubReadError) -> str:
    if exc.status in (401, 403):
        return "UNKNOWN_PERMISSION_OR_AUTH_ERROR"
    if exc.status == 404:
        # GitHub may intentionally hide resources when permissions are insufficient.
        return "UNKNOWN_NOT_FOUND_OR_HIDDEN"
    return f"UNKNOWN_HTTP_{exc.status}"


def assess(repo: str, token: str | None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "agent": "AIGC Repository Administrator Agent",
        "mode": "READ_ONLY",
        "repository": repo,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "BLOCK",
        "checks": {},
        "required_actions": [],
        "limitations": [
            "This assessment is advisory and read-only; it does not change repository settings.",
            "API visibility is not proof that every setting is effective; enforcement testing and independent review are required.",
            "A green CI run alone is not release provenance and does not authorize release.",
        ],
    }

    try:
        metadata = github_get(repo, "", token)
        default_branch = metadata.get("default_branch")
        report["checks"]["repository_metadata"] = {
            "status": "PASS" if default_branch else "BLOCK",
            "default_branch": default_branch,
            "private": metadata.get("private"),
            "archived": metadata.get("archived"),
        }
    except GitHubReadError as exc:
        report["checks"]["repository_metadata"] = {
            "status": error_state(exc), "http_status": exc.status
        }
        report["required_actions"].append(
            "Provide a valid read-only GitHub token and confirm repository access; do not infer missing settings from an API error."
        )
        return report

    if default_branch != "main":
        report["required_actions"].append(
            f"Confirm the intended protected default/release branch; observed default branch is {default_branch!r}, not 'main'."
        )

    try:
        rulesets = github_get(repo, "rulesets?includes_parents=true", token)
        if not isinstance(rulesets, list):
            raise RuntimeError("Rulesets endpoint returned an unexpected schema.")
        active = [
            rule for rule in rulesets
            if isinstance(rule, dict) and rule.get("enforcement") == "active"
        ]
        # Presence of an active ruleset is not proof that its target, rules,
        # bypass actors, or conditions meet the required policy. This first
        # version reports presence only and therefore cannot mark the gate PASS.
        report["checks"]["rulesets"] = {
            "status": "BLOCK",
            "visible_count": len(rulesets),
            "active_count": len(active),
            "rulesets": [
                {
                    "id": rule.get("id"),
                    "name": rule.get("name"),
                    "enforcement": rule.get("enforcement"),
                    "target": rule.get("target"),
                    "source_type": rule.get("source_type"),
                    "source": rule.get("source"),
                }
                for rule in rulesets if isinstance(rule, dict)
            ],
        }
        if not active:
            report["required_actions"].append(
                "Repository administrator: create and activate a ruleset targeting main and a release-tag ruleset (confirm the actual tag naming convention first)."
            )
        else:
            report["required_actions"].append(
                "Inspect each active ruleset's full detail response, target refs, required rules, and bypass actors; active ruleset presence alone is not a pass."
            )
    except GitHubReadError as exc:
        report["checks"]["rulesets"] = {
            "status": error_state(exc), "http_status": exc.status
        }
        report["required_actions"].append(
            "Obtain read access to repository rulesets and rerun; an unreadable endpoint is UNKNOWN, not proof of protection."
        )
    except RuntimeError as exc:
        report["checks"]["rulesets"] = {"status": "UNKNOWN_SCHEMA", "detail": str(exc)}
        report["required_actions"].append("Inspect the rulesets response schema manually and rerun.")

    branch = default_branch or "main"
    try:
        protection = github_get(repo, f"branches/{branch}/protection", token)
        reviews = protection.get("required_pull_request_reviews") or {}
        checks = protection.get("required_status_checks") or {}
        contexts = checks.get("contexts") or []
        strict = checks.get("strict")
        restrictions = protection.get("restrictions")
        protected = bool(reviews) and bool(checks) and bool(contexts)
        report["checks"]["branch_protection"] = {
            "status": "PASS" if protected else "BLOCK",
            "branch": branch,
            "required_reviews": reviews.get("required_approving_review_count"),
            "dismiss_stale_reviews": reviews.get("dismiss_stale_reviews"),
            "require_code_owner_reviews": reviews.get("require_code_owner_reviews"),
            "required_status_contexts": contexts,
            "require_up_to_date_branch": strict,
            "enforce_admins": (protection.get("enforce_admins") or {}).get("enabled"),
            "push_restrictions_present": restrictions is not None,
            "allows_force_pushes": (protection.get("allow_force_pushes") or {}).get("enabled"),
            "allows_deletions": (protection.get("allow_deletions") or {}).get("enabled"),
        }
        if not protected:
            report["required_actions"].append(
                f"Configure required pull-request review and exact required status-check contexts on {branch}, then read back and test enforcement."
            )
        if (protection.get("allow_force_pushes") or {}).get("enabled") is True:
            report["required_actions"].append(f"Disable force pushes on protected branch {branch}.")
        if (protection.get("allow_deletions") or {}).get("enabled") is True:
            report["required_actions"].append(f"Disable deletion of protected branch {branch}.")
    except GitHubReadError as exc:
        report["checks"]["branch_protection"] = {
            "status": error_state(exc), "http_status": exc.status, "branch": branch
        }
        report["required_actions"].append(
            f"Read protection settings for {branch}; 404/403 is ambiguous and must be resolved by a repository administrator."
        )

    # Ruleset metadata is not enough to prove exact tag coverage without inspecting
    # each rule's conditions and rules. Record a separate mandatory verification.
    ruleset_check = report["checks"].get("rulesets", {})
    tag_covered = False
    for rule in ruleset_check.get("rulesets", []):
        conditions = rule.get("conditions") or {}
        ref_name = conditions.get("ref_name") or {}
        include = ref_name.get("include") or []
        exclude = ref_name.get("exclude") or []
        if rule.get("enforcement") == "active" and any(
            pattern == f"refs/tags/{REQUIRED_TAG_PATTERN_HINT}"
            for pattern in include
        ) and not exclude:
            tag_covered = True
    report["checks"]["release_tag_protection"] = {
        # A matching include pattern alone is insufficient without verifying
        # the detailed rules that prevent tag updates/deletion and bypass.
        "status": "BLOCK",
        "pattern_hint": REQUIRED_TAG_PATTERN_HINT,
        "note": "Confirm actual tag convention and inspect rule conditions, update/delete restrictions, and bypass actors manually.",
    }
    if not tag_covered:
        report["required_actions"].append(
            "Verify an active ruleset covers the actual release-tag pattern and prohibits tag updates/deletion; do not assume v* is correct without inspecting existing tags."
        )

    report["required_actions"].extend([
        "Review the attestation producer source and pin it to an independently verified immutable full commit SHA.",
        "Generate separate signed attestations for the actual canonical receipt bundle and actual release artifact from a protected trusted workflow.",
        "Verify both attestations against the exact source commit/tree, trusted workflow/certificate identity, predicate type, and local subject SHA-256; preserve raw output and run metadata.",
        "Run real signed adversarial integration tests and all substantive release checkers; obtain independent review of the complete evidence chain.",
        "Keep Release Assurance decision BLOCK until every mandatory gate has fresh, independently verifiable evidence.",
    ])

    statuses = [value.get("status", "UNKNOWN") for value in report["checks"].values()]
    # This implementation deliberately cannot assert full protection until
    # it fetches and evaluates each ruleset's detailed rules and bypass actors.
    all_protection_checks_pass = False
    report["decision"] = "BLOCK"  # This read-only settings audit cannot approve a release.
    report["repository_protection_assessment"] = (
        "PROTECTION_READBACK_PARTIAL_PASS" if all_protection_checks_pass else "BLOCK"
    )
    report["observed_check_statuses"] = statuses
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub owner/repository")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    try:
        report = assess(args.repo, token)
    except Exception as exc:
        report = {
            "agent": "AIGC Repository Administrator Agent",
            "mode": "READ_ONLY",
            "repository": args.repo,
            "decision": "BLOCK",
            "error": str(exc),
            "required_actions": [
                "Resolve the read/API error and rerun; do not infer that protection or release gates passed."
            ],
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("repository_protection_assessment") == "PROTECTION_READBACK_PARTIAL_PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
