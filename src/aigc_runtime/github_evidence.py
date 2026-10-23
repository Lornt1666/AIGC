"""Read-only live GitHub evidence acquisition for RX-148.

Requires GITHUB_TOKEN (or an explicitly named environment variable) with read-only
repository/pull-request/actions permissions. All API failures, pagination failures,
and insufficient protection permissions are represented as unavailable evidence.
No writes, merges, deployments, or releases are performed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Mapping

API = "https://api.github.com"
USER_AGENT = "AIGC-RX148-EvidenceCollector/1.0"
READ_ONLY_PERMISSIONS = ("contents:read", "pull_requests:read", "actions:read")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubEvidenceError(RuntimeError):
    """Raised when live evidence cannot be acquired completely and safely."""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class GitHubReadOnlyClient:
    def __init__(self, token: str, *, timeout: float = 15.0, max_pages: int = 20,
                 opener: Callable[..., Any] | None = None):
        if not token or not token.strip():
            raise GitHubEvidenceError("github_token_required")
        if timeout <= 0 or max_pages < 1:
            raise GitHubEvidenceError("invalid_client_limits")
        self._token = token.strip()
        self.timeout = timeout
        self.max_pages = max_pages
        self._opener = opener or urllib.request.build_opener(_NoRedirect()).open

    def get(self, url: str) -> tuple[Any, Mapping[str, str]]:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "api.github.com":
            raise GitHubEvidenceError("url_not_allowlisted")
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + self._token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }, method="GET")
        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read()
                headers = {k.lower(): v for k, v in response.headers.items()}
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 404):
                raise GitHubEvidenceError("github_api_unavailable:" + str(exc.code)) from exc
            raise GitHubEvidenceError("github_api_http_error:" + str(exc.code)) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GitHubEvidenceError("github_api_transport_error:" + type(exc).__name__) from exc
        if status != 200:
            raise GitHubEvidenceError("github_api_unexpected_status:" + str(status))
        try:
            return json.loads(raw.decode("utf-8")), headers
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise GitHubEvidenceError("github_api_invalid_json") from exc

    def get_collection(self, url: str, collection_key: str | None = None) -> list[Any]:
        """Fetch a complete REST collection, handling GitHub's object-wrapped arrays."""
        items: list[Any] = []
        next_url = url
        seen: set[str] = set()
        for _ in range(self.max_pages):
            if next_url in seen:
                raise GitHubEvidenceError("pagination_loop_detected")
            seen.add(next_url)
            payload, headers = self.get(next_url)
            if isinstance(payload, list):
                page = payload
            elif isinstance(payload, Mapping) and collection_key and isinstance(payload.get(collection_key), list):
                page = payload[collection_key]
            else:
                raise GitHubEvidenceError("expected_collection_response:" + str(collection_key))
            items.extend(page)
            link = headers.get("link", "")
            next_link = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    left, right = part.find("<"), part.find(">")
                    if left >= 0 and right > left:
                        next_link = part[left + 1:right]
            if not next_link:
                return items
            parsed = urllib.parse.urlparse(next_link)
            if parsed.scheme != "https" or parsed.hostname != "api.github.com":
                raise GitHubEvidenceError("pagination_url_not_allowlisted")
            next_url = next_link
        raise GitHubEvidenceError("pagination_limit_exceeded")

    def get_all(self, url: str) -> list[Any]:
        items: list[Any] = []
        next_url = url
        seen: set[str] = set()
        for _ in range(self.max_pages):
            if next_url in seen:
                raise GitHubEvidenceError("pagination_loop_detected")
            seen.add(next_url)
            payload, headers = self.get(next_url)
            if not isinstance(payload, list):
                raise GitHubEvidenceError("expected_collection_response")
            items.extend(payload)
            link = headers.get("link", "")
            next_link = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    left = part.find("<")
                    right = part.find(">")
                    if left >= 0 and right > left:
                        next_link = part[left + 1:right]
            if not next_link:
                return items
            parsed = urllib.parse.urlparse(next_link)
            if parsed.scheme != "https" or parsed.hostname != "api.github.com":
                raise GitHubEvidenceError("pagination_url_not_allowlisted")
            next_url = next_link
        raise GitHubEvidenceError("pagination_limit_exceeded")


def _safe_repo(repo: str) -> str:
    bits = repo.split("/") if isinstance(repo, str) else []
    if len(bits) != 2 or any(not b or b in (".", "..") or not all(c.isalnum() or c in "-_." for c in b) for b in bits):
        raise GitHubEvidenceError("repository_name_invalid")
    return "/".join(urllib.parse.quote(x, safe="-_.") for x in bits)


def acquire_live_snapshot(repository: str, pr_number: int, *,
                          token_env: str = "GITHUB_TOKEN",
                          required_ci_jobs: list[str] | None = None,
                          release_branch: str = "main",
                          client: GitHubReadOnlyClient | None = None) -> dict[str, Any]:
    """Fetch current PR, CI/checks, reviews, and protection readback.

    Protection API 403/404 is explicitly UNVERIFIABLE; it is never treated as absent
    or as proof that protection is disabled. Cryptographic receipt verification is
    delegated to the separate trusted-key verifier.
    """
    repo = _safe_repo(repository)
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number < 1:
        raise GitHubEvidenceError("pr_number_invalid")
    api = client or GitHubReadOnlyClient(os.environ.get(token_env, ""))
    root = API + "/repos/" + repo
    observed_at = _iso_now()
    pr, _ = api.get(root + "/pulls/" + str(pr_number))
    if not isinstance(pr, Mapping) or not isinstance(pr.get("head"), Mapping) or not isinstance(pr.get("base"), Mapping):
        raise GitHubEvidenceError("pull_request_response_malformed")
    head = pr["head"].get("sha")
    base_sha = pr["base"].get("sha")
    base_branch = pr["base"].get("ref")
    if not isinstance(head, str) or len(head) != 40 or not isinstance(base_sha, str) or len(base_sha) != 40:
        raise GitHubEvidenceError("pull_request_sha_missing_or_invalid")
    # GitHub returns workflow runs in an object-wrapped collection; paginate the named array.
    all_runs = api.get_collection(root + "/actions/runs?head_sha=" + head + "&per_page=100", "workflow_runs")
    ci_runs: list[dict[str, Any]] = []
    for run in all_runs:
        if not isinstance(run, Mapping) or run.get("head_sha") != head:
            continue
        run_id = run.get("id")
        attempt = run.get("run_attempt", 1)
        if not isinstance(run_id, int) or not isinstance(attempt, int):
            continue
        jobs = api.get_collection(root + "/actions/runs/" + str(run_id) + "/attempts/" + str(attempt) + "/jobs?per_page=100", "jobs")
        artifact_rows = api.get_collection(root + "/actions/runs/" + str(run_id) + "/artifacts?per_page=100", "artifacts") if run.get("status") == "completed" and run.get("conclusion") == "success" else []
        ci_runs.append({
            "run_id": run_id, "run_attempt": attempt, "head_sha": run.get("head_sha"),
            "status": run.get("status"), "conclusion": run.get("conclusion"),
            "event": run.get("event"), "workflow_id": run.get("workflow_id"),
            "jobs": [{"id": j.get("id"), "name": j.get("name"), "status": j.get("status"),
                      "conclusion": j.get("conclusion"), "head_sha": head}
                     for j in jobs if isinstance(j, Mapping)],
            "artifacts": [{"id": a.get("id"), "name": a.get("name"), "digest": a.get("digest"),
                           "size_in_bytes": a.get("size_in_bytes"), "expired": a.get("expired"),
                           "workflow_run_id": (a.get("workflow_run") or {}).get("id") if isinstance(a.get("workflow_run"), Mapping) else run_id,
                           "workflow_run_head_sha": (a.get("workflow_run") or {}).get("head_sha") if isinstance(a.get("workflow_run"), Mapping) else head}
                          for a in artifact_rows if isinstance(a, Mapping)],
        })
    reviews = api.get_collection(root + "/pulls/" + str(pr_number) + "/reviews?per_page=100")
    review_comments = api.get_collection(root + "/pulls/" + str(pr_number) + "/comments?per_page=100")
    commit_status, _ = api.get(root + "/commits/" + head + "/status")
    commit_statuses = api.get_collection(root + "/commits/" + head + "/statuses?per_page=100")
    check_runs = api.get_collection(root + "/commits/" + head + "/check-runs?per_page=100", "check_runs")
    protections = {}
    for branch_name in sorted({str(base_branch), release_branch}):
        encoded = urllib.parse.quote(branch_name, safe="")
        try:
            protection, _ = api.get(root + "/branches/" + encoded + "/protection")
            protections[branch_name] = {"status": "READ_BACK", "payload": protection}
        except GitHubEvidenceError as exc:
            protections[branch_name] = {"status": "UNVERIFIABLE", "reason": str(exc)}
    # Re-read PR metadata after collecting evidence to detect concurrent head/base changes.
    final_pr, _ = api.get(root + "/pulls/" + str(pr_number))
    final_head = final_pr.get("head", {}).get("sha") if isinstance(final_pr, Mapping) else None
    final_base_sha = final_pr.get("base", {}).get("sha") if isinstance(final_pr, Mapping) else None
    if not isinstance(final_head, str) or len(final_head) != 40:
        raise GitHubEvidenceError("final_live_head_missing_or_invalid")
    return {
        "schema_version": "rx148.github-snapshot.v1",
        "repository": repository, "pr_number": pr_number,
        "candidate_sha": head, "observed_head_sha": final_head,
        "base_branch": base_branch, "base_sha": final_base_sha,
        "acquisition_head_sha": head, "acquisition_base_sha": base_sha,
        "head_changed_during_acquisition": final_head != head or final_base_sha != base_sha,
        "evaluation_time": _iso_now(),
        "pr_state": pr.get("state"), "pr_draft": pr.get("draft"), "pr_merged": pr.get("merged"),
        "live_observation_authenticated": True, "observation_source": "github_api",
        "observed_at": observed_at, "acquisition_completed_at": _iso_now(),
        "required_ci_jobs": required_ci_jobs or [],
        "ci_runs": ci_runs,
        "commit_status": commit_status, "commit_statuses": commit_statuses, "check_runs": check_runs,
        "reviews": reviews, "review_comments": review_comments,
        "review_threads": {"status": "UNVERIFIABLE", "reason": "review-thread resolution requires a separately authorized GraphQL acquisition adapter; REST comments are not equivalent"},
        "protection_readbacks": protections,
        "protection": {"status": "UNVERIFIABLE", "authenticated": False,
                       "reason": "GitHub API readback is not itself an authenticated administrator receipt; verify a signed admin receipt separately"},
        "acquisition": {"complete": True, "read_only": True, "api_origin": API,
                        "limitations": ["artifact download/hash verification not performed",
                                        "GitHub REST JSON does not cryptographically authenticate reviewer identity or human acceptance",
                                        "protection readback needs authorized evidence and independent verification"]},
    }
