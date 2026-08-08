from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker


DEFAULT_CONFIG_PATH = Path("config/cloud_advancement_loop.json")
DEFAULT_SCHEMA_PATH = Path("schemas/cloud_advancement_loop.schema.json")
DEFAULT_EXECUTION_RECEIPT_SCHEMA_PATH = Path(
    "schemas/cloud_advancement_execution_receipt.schema.json"
)
TERMINAL_EVENT_TYPES = {"completed", "blocked", "failed", "expired"}
EVENT_TYPES = {"claimed", *TERMINAL_EVENT_TYPES}
SAFE_EXECUTORS = {"baseline_snapshot", "github_actions_gate"}
SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "client_secret",
    "cookie",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
}
SECRET_VALUE_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

CommandRunner = Callable[[Sequence[str], Path], Mapping[str, Any]]


class CloudAdvancementError(ValueError):
    """Raised when the cloud advancement loop would violate its contract."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CloudAdvancementError(
            f"Invalid timestamp in cloud advancement state: {value!r}."
        ) from exc
    if parsed.tzinfo is None:
        raise CloudAdvancementError(
            "Cloud advancement timestamps must include a timezone."
        )
    return parsed.astimezone(timezone.utc)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_program(
    project_root: Path,
    config_path: Path | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    config = _safe_input_path(
        root,
        config_path or DEFAULT_CONFIG_PATH,
        "cloud advancement config",
    )
    schema = _safe_input_path(
        root,
        schema_path or DEFAULT_SCHEMA_PATH,
        "cloud advancement schema",
    )
    payload = _load_json_object(config)
    schema_payload = _load_json_object(schema)
    _strict_validate(payload, schema_payload)
    validate_program(payload)
    return payload


def validate_program(program: Mapping[str, Any]) -> None:
    actions = list(program.get("actions", []))
    action_by_id: dict[str, Mapping[str, Any]] = {}
    stages: set[int] = set()
    priorities: set[int] = set()
    semantic_fingerprints: dict[str, str] = {}

    for action in actions:
        action_id = str(action.get("action_id", ""))
        if not action_id or action_id in action_by_id:
            raise CloudAdvancementError(
                f"Invalid or duplicate cloud action identifier: {action_id!r}."
            )
        action_by_id[action_id] = action

        stage = int(action.get("stage", -1))
        if stage in stages:
            raise CloudAdvancementError(
                f"Cloud action stage {stage} is duplicated."
            )
        stages.add(stage)

        priority = int(action.get("priority", -1))
        if priority in priorities:
            raise CloudAdvancementError(
                f"Cloud action priority {priority} is duplicated."
            )
        priorities.add(priority)

        fingerprint = action_semantic_fingerprint(action)
        if fingerprint in semantic_fingerprints:
            raise CloudAdvancementError(
                "Semantically duplicate cloud actions are prohibited: "
                f"{semantic_fingerprints[fingerprint]} and {action_id}."
            )
        semantic_fingerprints[fingerprint] = action_id

        execution_class = str(action.get("execution_class", ""))
        executor = str(action.get("executor", ""))
        phase5_required = action.get("phase5_required")
        if execution_class == "automatic_read_only":
            if executor not in SAFE_EXECUTORS or phase5_required is not False:
                raise CloudAdvancementError(
                    f"Read-only action {action_id} has an unsafe executor."
                )
        elif execution_class == "agent_internal":
            if executor != "agent_internal" or phase5_required is not False:
                raise CloudAdvancementError(
                    f"Internal action {action_id} has inconsistent authority."
                )
        elif execution_class == "phase5_external":
            if executor != "phase5_external" or phase5_required is not True:
                raise CloudAdvancementError(
                    f"External action {action_id} must remain Phase 5 gated."
                )
        else:
            raise CloudAdvancementError(
                f"Cloud action {action_id} has an unknown execution class."
            )

        retry_policy = str(action.get("retry_policy", ""))
        if retry_policy == "necessity_monitor":
            if executor != "github_actions_gate":
                raise CloudAdvancementError(
                    f"Only a governed observation may be a necessity monitor: "
                    f"{action_id}."
                )
            if int(action.get("retry_cooldown_hours", 0)) < 1:
                raise CloudAdvancementError(
                    f"Necessity monitor {action_id} requires a cooldown."
                )
        elif retry_policy == "never":
            if int(action.get("max_attempts", 0)) != 1:
                raise CloudAdvancementError(
                    f"Non-retry action {action_id} must allow one attempt."
                )
        elif retry_policy != "operator_necessity_only":
            raise CloudAdvancementError(
                f"Cloud action {action_id} has an unknown retry policy."
            )

    expected_stages = list(range(1, len(actions) + 1))
    actual_stages = [int(action["stage"]) for action in actions]
    if actual_stages != expected_stages:
        raise CloudAdvancementError(
            "Cloud actions must be listed once in contiguous dependency order."
        )

    for action in actions:
        action_id = str(action["action_id"])
        dependencies = [str(item) for item in action.get("dependencies", [])]
        for dependency in dependencies:
            if dependency not in action_by_id:
                raise CloudAdvancementError(
                    f"Cloud action {action_id} has unknown dependency "
                    f"{dependency}."
                )
            if int(action_by_id[dependency]["stage"]) >= int(action["stage"]):
                raise CloudAdvancementError(
                    f"Cloud action {action_id} depends on a non-earlier action."
                )
    _assert_acyclic(action_by_id)

    if not actions or actions[0].get("executor") != "baseline_snapshot":
        raise CloudAdvancementError(
            "The first cloud action must establish the local baseline."
        )
    if actions[-1].get("execution_class") != "phase5_external":
        raise CloudAdvancementError(
            "The final cloud action must remain Phase 5 gated."
        )

    safety = dict(program.get("safety", {}))
    for key in {
        "direct_main_write_allowed",
        "automatic_merge_allowed",
        "git_push_allowed_by_loop",
        "terraform_apply_allowed",
        "provider_resource_mutation_allowed",
        "credential_access_allowed",
        "raw_secrets_in_state_or_evidence_allowed",
        "external_action_performed",
    }:
        if safety.get(key) is not False:
            raise CloudAdvancementError(
                f"Cloud advancement safety control {key} is weakened."
            )
    if safety.get("phase5_required_for_external_mutation") is not True:
        raise CloudAdvancementError(
            "External cloud mutation must require Phase 5."
        )


def validate_execution_receipt(
    project_root: Path,
    receipt_path: Path,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    receipt_file = _safe_input_path(
        root,
        receipt_path,
        "cloud advancement execution receipt",
    )
    schema_file = _safe_input_path(
        root,
        schema_path or DEFAULT_EXECUTION_RECEIPT_SCHEMA_PATH,
        "cloud advancement execution receipt schema",
    )
    receipt = _load_json_object(receipt_file)
    schema = _load_json_object(schema_file)
    _strict_validate(receipt, schema)
    digest_basis = dict(receipt)
    recorded_digest = str(digest_basis.pop("receipt_digest", ""))
    if recorded_digest != canonical_digest(digest_basis):
        raise CloudAdvancementError(
            "Cloud advancement execution receipt digest is invalid."
        )
    return receipt


def action_semantic_fingerprint(action: Mapping[str, Any]) -> str:
    basis = {
        "category": _normalize_text(action.get("category", "")),
        "objective": _normalize_text(action.get("objective", "")),
        "required_outputs": sorted(
            _normalize_text(item)
            for item in action.get("required_outputs", [])
        ),
        "acceptance_checks": sorted(
            _normalize_text(item)
            for item in action.get("acceptance_checks", [])
        ),
    }
    return canonical_digest(basis)


def repository_revision_state(project_root: Path) -> tuple[str, str]:
    root = project_root.resolve()
    revision = _git_output(root, ["rev-parse", "HEAD"]) or "unbound"
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return revision, "unbound"
    if result.returncode != 0:
        return revision, "unbound"
    return revision, "clean" if not result.stdout.strip() else "dirty"


class CloudAdvancementStore:
    def __init__(
        self,
        project_root: Path,
        program: Mapping[str, Any],
        state_path: Path | None = None,
    ):
        self.root = project_root.resolve()
        self.program = dict(program)
        self.action_by_id = {
            str(action["action_id"]): dict(action)
            for action in self.program["actions"]
        }
        configured = Path(str(self.program["state"]["sqlite_path"]))
        self.state_path = _safe_runtime_path(
            self.root,
            state_path or configured,
            "cloud advancement state database",
        )
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def claim_next(
        self,
        *,
        actor: str,
        now: datetime | None = None,
        allow_agent_internal: bool = True,
    ) -> dict[str, Any]:
        observed_at = now or utc_now()
        revision, source_state = repository_revision_state(self.root)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._validate_history(connection)
            expired = self._expire_stale_claims(
                connection,
                observed_at,
                actor,
                revision,
                source_state,
            )
            active = self._active_claims(connection)
            if active:
                connection.commit()
                return {
                    "status": "active_claim_exists",
                    "active_run": active[0],
                    "expired_claims": expired,
                    "external_action_performed": False,
                }

            states = self._derive_action_states(connection, observed_at)
            candidates: list[tuple[Mapping[str, Any], str]] = []
            blocked_reasons: list[dict[str, str]] = []
            for action in self.program["actions"]:
                action_id = str(action["action_id"])
                eligibility, reason = self._eligibility(
                    action,
                    states,
                    source_state,
                    observed_at,
                    allow_agent_internal,
                )
                if eligibility:
                    candidates.append((action, reason))
                else:
                    blocked_reasons.append(
                        {"action_id": action_id, "reason": reason}
                    )

            if not candidates:
                connection.commit()
                return {
                    "status": "no_eligible_action",
                    "source_revision": revision,
                    "source_state": source_state,
                    "blocked_reasons": blocked_reasons,
                    "expired_claims": expired,
                    "external_action_performed": False,
                }

            action, selection_reason = sorted(
                candidates,
                key=lambda item: (
                    -int(item[0]["priority"]),
                    int(item[0]["stage"]),
                    str(item[0]["action_id"]),
                ),
            )[0]
            action_id = str(action["action_id"])
            attempt = int(states[action_id]["attempts"]) + 1
            run_id = (
                f"CLOUD-RUN-{action_id}-"
                + uuid.uuid4().hex[:12].upper()
            )
            necessity_reason = (
                "Scheduled re-observation is necessary because the external "
                "hosted-CI gate remains unresolved after the governed cooldown."
                if attempt > 1
                else ""
            )
            self._append_event(
                connection,
                run_id=run_id,
                action_id=action_id,
                event_type="claimed",
                occurred_at=observed_at,
                attempt=attempt,
                actor=actor,
                source_revision=revision,
                source_state=source_state,
                necessity_reason=necessity_reason,
                evidence={
                    "selection_reason": selection_reason,
                    "action_fingerprint": action_semantic_fingerprint(action),
                },
            )
            connection.commit()
            return {
                "status": "claimed",
                "run_id": run_id,
                "attempt": attempt,
                "selection_reason": selection_reason,
                "necessity_reason": necessity_reason,
                "source_revision": revision,
                "source_state": source_state,
                "action": dict(action),
                "external_action_performed": False,
            }

    def complete(
        self,
        run_id: str,
        *,
        actor: str,
        evidence: Mapping[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        observed_at = now or utc_now()
        _assert_safe_evidence(evidence)
        revision, source_state = repository_revision_state(self.root)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._validate_history(connection)
            claim = self._require_active_claim(connection, run_id)
            action = self.action_by_id[str(claim["action_id"])]
            if action["execution_class"] == "phase5_external":
                raise CloudAdvancementError(
                    "The local loop cannot complete a Phase 5 external action."
                )
            self._append_event(
                connection,
                run_id=run_id,
                action_id=str(claim["action_id"]),
                event_type="completed",
                occurred_at=observed_at,
                attempt=int(claim["attempt"]),
                actor=actor,
                source_revision=revision,
                source_state=source_state,
                necessity_reason=str(claim["necessity_reason"]),
                evidence=dict(evidence),
            )
            connection.commit()
        return {
            "status": "completed",
            "run_id": run_id,
            "action_id": claim["action_id"],
            "external_action_performed": False,
        }

    def retry_action(
        self,
        action_id: str,
        *,
        actor: str,
        necessity_reason: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        observed_at = now or utc_now()
        if action_id not in self.action_by_id:
            raise CloudAdvancementError(
                f"Unknown cloud action identifier: {action_id}."
            )
        if len(necessity_reason.strip()) < 20:
            raise CloudAdvancementError(
                "A repeated action requires a substantive necessity reason."
            )
        revision, source_state = repository_revision_state(self.root)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._validate_history(connection)
            self._expire_stale_claims(
                connection,
                observed_at,
                actor,
                revision,
                source_state,
            )
            active = self._active_claims(connection)
            if active:
                raise CloudAdvancementError(
                    "A cloud action is already active."
                )
            states = self._derive_action_states(connection, observed_at)
            state = states[action_id]
            action = self.action_by_id[action_id]
            attempts = int(state["attempts"])
            if attempts == 0:
                raise CloudAdvancementError(
                    "A first attempt must be selected by claim-next."
                )
            if state["state"] == "completed":
                raise CloudAdvancementError(
                    "Completed cloud actions can never be retried."
                )
            if attempts >= int(action["max_attempts"]):
                raise CloudAdvancementError(
                    f"Cloud action {action_id} reached its attempt limit."
                )
            if action["retry_policy"] == "never":
                raise CloudAdvancementError(
                    f"Cloud action {action_id} prohibits retries."
                )
            if action["execution_class"] == "phase5_external":
                raise CloudAdvancementError(
                    "The local loop cannot retry a Phase 5 external action."
                )
            if (
                action["requires_clean_worktree"] is True
                and source_state != "clean"
            ):
                raise CloudAdvancementError(
                    f"Cloud action {action_id} requires a clean worktree."
                )
            incomplete_dependencies = [
                dependency
                for dependency in action["dependencies"]
                if states[str(dependency)]["state"] != "completed"
            ]
            if incomplete_dependencies:
                raise CloudAdvancementError(
                    f"Cloud action {action_id} has incomplete dependencies: "
                    f"{incomplete_dependencies}."
                )
            retry_not_before = str(state["retry_not_before"])
            if (
                retry_not_before
                and observed_at < parse_datetime(retry_not_before)
            ):
                raise CloudAdvancementError(
                    f"Cloud action {action_id} remains in retry cooldown."
                )

            run_id = (
                f"CLOUD-RUN-{action_id}-"
                + uuid.uuid4().hex[:12].upper()
            )
            self._append_event(
                connection,
                run_id=run_id,
                action_id=action_id,
                event_type="claimed",
                occurred_at=observed_at,
                attempt=attempts + 1,
                actor=actor,
                source_revision=revision,
                source_state=source_state,
                necessity_reason=necessity_reason.strip(),
                evidence={
                    "selection_reason": "explicit_recorded_necessity",
                    "prior_state": state["state"],
                    "action_fingerprint": action_semantic_fingerprint(action),
                },
            )
            connection.commit()
        return {
            "status": "claimed",
            "run_id": run_id,
            "action_id": action_id,
            "attempt": attempts + 1,
            "selection_reason": "explicit_recorded_necessity",
            "necessity_reason": necessity_reason.strip(),
            "source_revision": revision,
            "source_state": source_state,
            "action": dict(action),
            "external_action_performed": False,
        }

    def block(
        self,
        run_id: str,
        *,
        actor: str,
        blocker_key: str,
        blocker_fingerprint: str,
        reason: str,
        evidence: Mapping[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        observed_at = now or utc_now()
        _assert_safe_evidence(evidence)
        if not blocker_key.strip() or not reason.strip():
            raise CloudAdvancementError(
                "Blocked cloud actions require a blocker and reason."
            )
        if not re.fullmatch(r"[a-f0-9]{64}", blocker_fingerprint):
            raise CloudAdvancementError(
                "Blocker fingerprint must be a SHA-256 digest."
            )
        revision, source_state = repository_revision_state(self.root)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._validate_history(connection)
            claim = self._require_active_claim(connection, run_id)
            action = self.action_by_id[str(claim["action_id"])]
            retry_not_before = observed_at + timedelta(
                hours=int(action["retry_cooldown_hours"])
            )
            necessity_reason = (
                "A future repeat is permitted only to determine whether this "
                "recorded blocker changed after the governed cooldown."
                if action["retry_policy"] == "necessity_monitor"
                else ""
            )
            self._append_event(
                connection,
                run_id=run_id,
                action_id=str(claim["action_id"]),
                event_type="blocked",
                occurred_at=observed_at,
                attempt=int(claim["attempt"]),
                actor=actor,
                source_revision=revision,
                source_state=source_state,
                necessity_reason=necessity_reason,
                blocker_key=blocker_key.strip(),
                blocker_fingerprint=blocker_fingerprint,
                retry_not_before=retry_not_before,
                evidence={"reason": reason.strip(), **dict(evidence)},
            )
            connection.commit()
        return {
            "status": "blocked",
            "run_id": run_id,
            "action_id": claim["action_id"],
            "retry_not_before": isoformat(retry_not_before),
            "external_action_performed": False,
        }

    def status(self, now: datetime | None = None) -> dict[str, Any]:
        observed_at = now or utc_now()
        revision, source_state = repository_revision_state(self.root)
        with self._connect() as connection:
            self._validate_history(connection)
            events = self._read_events(connection)
            states = self._derive_action_states(connection, observed_at)
            active = self._active_claims(connection)

        action_results: list[dict[str, Any]] = []
        for action in self.program["actions"]:
            action_id = str(action["action_id"])
            state = dict(states[action_id])
            eligibility, reason = self._eligibility(
                action,
                states,
                source_state,
                observed_at,
                True,
            )
            state.update(
                {
                    "action_id": action_id,
                    "title": action["title"],
                    "stage": action["stage"],
                    "dependencies": action["dependencies"],
                    "execution_class": action["execution_class"],
                    "eligible": eligibility,
                    "eligibility_reason": reason,
                    "semantic_fingerprint": action_semantic_fingerprint(action),
                }
            )
            action_results.append(state)

        completed = [
            item["action_id"]
            for item in action_results
            if item["state"] == "completed"
        ]
        return {
            "program_id": self.program["program_id"],
            "program_version": self.program["version"],
            "program_digest": canonical_digest(self.program),
            "observed_at": isoformat(observed_at),
            "source_revision": revision,
            "source_state": source_state,
            "state_path": _relative_or_absolute(self.root, self.state_path),
            "event_count": len(events),
            "history_head_sha256": (
                events[-1]["event_hash"] if events else "0" * 64
            ),
            "active_claims": active,
            "completed_action_ids": completed,
            "completed_action_count": len(completed),
            "total_action_count": len(action_results),
            "action_results": action_results,
            "duplicate_prevention": {
                "semantic_fingerprints_unique": True,
                "completed_actions_reselected": False,
                "one_active_claim_enforced": True,
                "retries_require_necessity": True,
                "program_bound_hash_chain_valid": True,
            },
            "governance": {
                "operator_review_required": True,
                "phase5_approval_present": False,
                "git_push_allowed_by_loop": False,
                "terraform_apply_allowed": False,
                "provider_resource_mutation_allowed": False,
                "credential_access_performed": False,
                "external_action_performed": False,
            },
        }

    def events(self, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1 or limit > 1000:
            raise CloudAdvancementError("Event limit must be within 1..1000.")
        with self._connect() as connection:
            self._validate_history(connection)
            rows = connection.execute(
                """
                SELECT *
                FROM cloud_action_events
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._event_to_dict(row) for row in reversed(rows)]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cloud_action_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    run_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    event_type TEXT NOT NULL CHECK (
                        event_type IN (
                            'claimed',
                            'completed',
                            'blocked',
                            'failed',
                            'expired'
                        )
                    ),
                    occurred_at TEXT NOT NULL,
                    attempt INTEGER NOT NULL CHECK (attempt >= 1),
                    actor TEXT NOT NULL,
                    source_revision TEXT NOT NULL,
                    source_state TEXT NOT NULL CHECK (
                        source_state IN ('clean', 'dirty', 'unbound')
                    ),
                    necessity_reason TEXT NOT NULL,
                    blocker_key TEXT NOT NULL,
                    blocker_fingerprint TEXT NOT NULL,
                    retry_not_before TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    program_digest TEXT NOT NULL,
                    previous_event_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    external_action_performed INTEGER NOT NULL
                        CHECK (external_action_performed = 0)
                );

                CREATE INDEX IF NOT EXISTS cloud_events_action_sequence
                    ON cloud_action_events(action_id, sequence);

                CREATE INDEX IF NOT EXISTS cloud_events_run_sequence
                    ON cloud_action_events(run_id, sequence);

                CREATE TRIGGER IF NOT EXISTS cloud_events_no_update
                BEFORE UPDATE ON cloud_action_events
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'cloud action history is append-only'
                    );
                END;

                CREATE TRIGGER IF NOT EXISTS cloud_events_no_delete
                BEFORE DELETE ON cloud_action_events
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'cloud action history is append-only'
                    );
                END;
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(cloud_action_events)"
                ).fetchall()
            }
            required_columns = {
                "program_digest",
                "previous_event_hash",
                "event_hash",
            }
            if not required_columns <= columns:
                raise CloudAdvancementError(
                    "Cloud advancement state predates the hash-chain contract; "
                    "preserve it for review and use a separately approved state "
                    "migration or a new database path."
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.state_path,
            timeout=30,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _append_event(
        self,
        connection: sqlite3.Connection,
        *,
        run_id: str,
        action_id: str,
        event_type: str,
        occurred_at: datetime,
        attempt: int,
        actor: str,
        source_revision: str,
        source_state: str,
        necessity_reason: str = "",
        blocker_key: str = "",
        blocker_fingerprint: str = "",
        retry_not_before: datetime | None = None,
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        if event_type not in EVENT_TYPES:
            raise CloudAdvancementError(
                f"Unsupported cloud event type: {event_type}."
            )
        if action_id not in self.action_by_id:
            raise CloudAdvancementError(
                f"Unknown cloud action identifier: {action_id}."
            )
        if not actor.strip():
            raise CloudAdvancementError("Cloud events require an actor.")
        payload = dict(evidence or {})
        _assert_safe_evidence(payload)
        event_id = f"CLOUD-EVENT-{uuid.uuid4().hex.upper()}"
        occurred_at_text = isoformat(occurred_at)
        retry_not_before_text = (
            isoformat(retry_not_before) if retry_not_before else ""
        )
        evidence_json = canonical_json(payload)
        program_digest = canonical_digest(self.program)
        previous_row = connection.execute(
            """
            SELECT event_hash
            FROM cloud_action_events
            ORDER BY sequence DESC
            LIMIT 1
            """
        ).fetchone()
        previous_event_hash = (
            str(previous_row["event_hash"])
            if previous_row
            else "0" * 64
        )
        event_hash = canonical_digest(
            {
                "event_id": event_id,
                "run_id": run_id,
                "action_id": action_id,
                "event_type": event_type,
                "occurred_at": occurred_at_text,
                "attempt": attempt,
                "actor": actor.strip(),
                "source_revision": source_revision,
                "source_state": source_state,
                "necessity_reason": necessity_reason,
                "blocker_key": blocker_key,
                "blocker_fingerprint": blocker_fingerprint,
                "retry_not_before": retry_not_before_text,
                "evidence_json": evidence_json,
                "program_digest": program_digest,
                "previous_event_hash": previous_event_hash,
                "external_action_performed": 0,
            }
        )
        connection.execute(
            """
            INSERT INTO cloud_action_events (
                event_id,
                run_id,
                action_id,
                event_type,
                occurred_at,
                attempt,
                actor,
                source_revision,
                source_state,
                necessity_reason,
                blocker_key,
                blocker_fingerprint,
                retry_not_before,
                evidence_json,
                program_digest,
                previous_event_hash,
                event_hash,
                external_action_performed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                event_id,
                run_id,
                action_id,
                event_type,
                occurred_at_text,
                attempt,
                actor.strip(),
                source_revision,
                source_state,
                necessity_reason,
                blocker_key,
                blocker_fingerprint,
                retry_not_before_text,
                evidence_json,
                program_digest,
                previous_event_hash,
                event_hash,
            ),
        )

    def _read_events(
        self,
        connection: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM cloud_action_events ORDER BY sequence"
        ).fetchall()
        return [self._event_to_dict(row) for row in rows]

    def _event_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "sequence": int(row["sequence"]),
            "event_id": str(row["event_id"]),
            "run_id": str(row["run_id"]),
            "action_id": str(row["action_id"]),
            "event_type": str(row["event_type"]),
            "occurred_at": str(row["occurred_at"]),
            "attempt": int(row["attempt"]),
            "actor": str(row["actor"]),
            "source_revision": str(row["source_revision"]),
            "source_state": str(row["source_state"]),
            "necessity_reason": str(row["necessity_reason"]),
            "blocker_key": str(row["blocker_key"]),
            "blocker_fingerprint": str(row["blocker_fingerprint"]),
            "retry_not_before": str(row["retry_not_before"]),
            "evidence": json.loads(str(row["evidence_json"])),
            "program_digest": str(row["program_digest"]),
            "previous_event_hash": str(row["previous_event_hash"]),
            "event_hash": str(row["event_hash"]),
            "external_action_performed": bool(
                row["external_action_performed"]
            ),
        }

    def _validate_history(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            "SELECT * FROM cloud_action_events ORDER BY sequence"
        ).fetchall()
        expected_program_digest = canonical_digest(self.program)
        previous_event_hash = "0" * 64
        for row in rows:
            if str(row["program_digest"]) != expected_program_digest:
                raise CloudAdvancementError(
                    "Cloud action history is bound to a different program."
                )
            if str(row["previous_event_hash"]) != previous_event_hash:
                raise CloudAdvancementError(
                    "Cloud action history chain is discontinuous."
                )
            expected_hash = canonical_digest(
                {
                    "event_id": str(row["event_id"]),
                    "run_id": str(row["run_id"]),
                    "action_id": str(row["action_id"]),
                    "event_type": str(row["event_type"]),
                    "occurred_at": str(row["occurred_at"]),
                    "attempt": int(row["attempt"]),
                    "actor": str(row["actor"]),
                    "source_revision": str(row["source_revision"]),
                    "source_state": str(row["source_state"]),
                    "necessity_reason": str(row["necessity_reason"]),
                    "blocker_key": str(row["blocker_key"]),
                    "blocker_fingerprint": str(
                        row["blocker_fingerprint"]
                    ),
                    "retry_not_before": str(row["retry_not_before"]),
                    "evidence_json": str(row["evidence_json"]),
                    "program_digest": str(row["program_digest"]),
                    "previous_event_hash": str(
                        row["previous_event_hash"]
                    ),
                    "external_action_performed": int(
                        row["external_action_performed"]
                    ),
                }
            )
            if str(row["event_hash"]) != expected_hash:
                raise CloudAdvancementError(
                    "Cloud action history event hash is invalid."
                )
            previous_event_hash = expected_hash

    def _active_claims(
        self,
        connection: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        events = self._read_events(connection)
        by_run: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            by_run.setdefault(str(event["run_id"]), []).append(event)
        active: list[dict[str, Any]] = []
        for run_events in by_run.values():
            claim = next(
                (
                    event
                    for event in run_events
                    if event["event_type"] == "claimed"
                ),
                None,
            )
            terminal = any(
                event["event_type"] in TERMINAL_EVENT_TYPES
                for event in run_events
            )
            if claim and not terminal:
                active.append(claim)
        return sorted(active, key=lambda item: int(item["sequence"]))

    def _expire_stale_claims(
        self,
        connection: sqlite3.Connection,
        observed_at: datetime,
        actor: str,
        revision: str,
        source_state: str,
    ) -> list[str]:
        expired: list[str] = []
        lease = timedelta(
            minutes=int(
                self.program["selection_policy"]["claim_lease_minutes"]
            )
        )
        for claim in self._active_claims(connection):
            claimed_at = parse_datetime(str(claim["occurred_at"]))
            if observed_at < claimed_at + lease:
                continue
            run_id = str(claim["run_id"])
            self._append_event(
                connection,
                run_id=run_id,
                action_id=str(claim["action_id"]),
                event_type="expired",
                occurred_at=observed_at,
                attempt=int(claim["attempt"]),
                actor=actor,
                source_revision=revision,
                source_state=source_state,
                necessity_reason=(
                    "Stale claim recovery is necessary to release the single "
                    "execution slot; the action is not automatically repeated."
                ),
                evidence={"expired_claimed_at": claim["occurred_at"]},
            )
            expired.append(run_id)
        return expired

    def _derive_action_states(
        self,
        connection: sqlite3.Connection,
        observed_at: datetime,
    ) -> dict[str, dict[str, Any]]:
        events = self._read_events(connection)
        by_action: dict[str, list[dict[str, Any]]] = {
            action_id: [] for action_id in self.action_by_id
        }
        for event in events:
            by_action[str(event["action_id"])].append(event)

        states: dict[str, dict[str, Any]] = {}
        for action_id, action_events in by_action.items():
            completed = any(
                event["event_type"] == "completed"
                for event in action_events
            )
            active = any(
                event["action_id"] == action_id
                for event in self._active_claims(connection)
            )
            claims = [
                event
                for event in action_events
                if event["event_type"] == "claimed"
            ]
            terminal_events = [
                event
                for event in action_events
                if event["event_type"] in TERMINAL_EVENT_TYPES
            ]
            latest_terminal = terminal_events[-1] if terminal_events else None
            state = "pending"
            if completed:
                state = "completed"
            elif active:
                state = "in_progress"
            elif latest_terminal:
                state = str(latest_terminal["event_type"])
            retry_not_before = (
                str(latest_terminal["retry_not_before"])
                if latest_terminal
                else ""
            )
            cooldown_elapsed = (
                bool(retry_not_before)
                and observed_at >= parse_datetime(retry_not_before)
            )
            states[action_id] = {
                "state": state,
                "attempts": len(claims),
                "latest_terminal_event": latest_terminal,
                "retry_not_before": retry_not_before,
                "cooldown_elapsed": cooldown_elapsed,
            }
        return states

    def _eligibility(
        self,
        action: Mapping[str, Any],
        states: Mapping[str, Mapping[str, Any]],
        source_state: str,
        observed_at: datetime,
        allow_agent_internal: bool,
    ) -> tuple[bool, str]:
        action_id = str(action["action_id"])
        state = states[action_id]
        if state["state"] == "completed":
            return False, "completed_actions_are_never_reselected"
        if state["state"] == "in_progress":
            return False, "action_already_has_an_active_claim"
        if action["execution_class"] == "phase5_external":
            return False, "phase5_external_action_requires_separate_authority"
        if (
            action["execution_class"] == "agent_internal"
            and not allow_agent_internal
        ):
            return False, "manual_agent_execution_required"
        incomplete_dependencies = [
            dependency
            for dependency in action["dependencies"]
            if states[str(dependency)]["state"] != "completed"
        ]
        if incomplete_dependencies:
            return (
                False,
                "dependencies_incomplete:" + ",".join(incomplete_dependencies),
            )
        if (
            action["requires_clean_worktree"] is True
            and source_state != "clean"
        ):
            return False, "clean_worktree_required"

        attempts = int(state["attempts"])
        if attempts == 0:
            return True, "first_attempt"
        if attempts >= int(action["max_attempts"]):
            return False, "maximum_attempts_reached"
        retry_policy = str(action["retry_policy"])
        if retry_policy == "never":
            return False, "retry_prohibited"
        if retry_policy == "operator_necessity_only":
            return False, "operator_necessity_record_required"
        if retry_policy == "necessity_monitor":
            retry_not_before = str(state["retry_not_before"])
            if not retry_not_before:
                return False, "monitor_retry_missing_cooldown"
            if observed_at < parse_datetime(retry_not_before):
                return False, "necessity_monitor_cooldown_active"
            return True, "necessity_monitor_after_cooldown"
        return False, "unsupported_retry_policy"

    def _require_active_claim(
        self,
        connection: sqlite3.Connection,
        run_id: str,
    ) -> dict[str, Any]:
        for claim in self._active_claims(connection):
            if claim["run_id"] == run_id:
                return claim
        raise CloudAdvancementError(
            f"Run {run_id!r} is not an active cloud action claim."
        )


def execute_next(
    project_root: Path,
    program: Mapping[str, Any],
    store: CloudAdvancementStore,
    *,
    actor: str,
    command_runner: CommandRunner | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_at = now or utc_now()
    claim = store.claim_next(
        actor=actor,
        now=observed_at,
        allow_agent_internal=False,
    )
    if claim["status"] != "claimed":
        return claim

    action = dict(claim["action"])
    executor = str(action["executor"])
    run_id = str(claim["run_id"])
    if executor == "baseline_snapshot":
        evidence = _baseline_evidence(project_root, program, claim)
        evidence_path = _write_runtime_evidence(
            project_root,
            program,
            run_id,
            "baseline_snapshot.json",
            evidence,
        )
        result = store.complete(
            run_id,
            actor=actor,
            evidence={
                "evidence_path": evidence_path,
                "evidence_sha256": canonical_digest(evidence),
                "validated_action_count": len(program["actions"]),
            },
            now=observed_at,
        )
        return {**result, "evidence": evidence}

    if executor == "github_actions_gate":
        observation = observe_github_actions_gate(
            project_root,
            program,
            command_runner=command_runner,
        )
        evidence_path = _write_runtime_evidence(
            project_root,
            program,
            run_id,
            "github_actions_gate.json",
            observation,
        )
        if observation["gate_passed"] is True:
            result = store.complete(
                run_id,
                actor=actor,
                evidence={
                    "evidence_path": evidence_path,
                    "evidence_sha256": canonical_digest(observation),
                    "observed_run_id": observation["run"]["databaseId"],
                    "executed_step_count": observation[
                        "executed_step_count"
                    ],
                },
                now=observed_at,
            )
            return {**result, "observation": observation}
        result = store.block(
            run_id,
            actor=actor,
            blocker_key="github_issue_124_hosted_ci_recovery",
            blocker_fingerprint=canonical_digest(observation),
            reason=(
                "Hosted CI recovery is not proven by a closed issue, exact-head "
                "successful run, and nonempty executed job steps."
            ),
            evidence={
                "evidence_path": evidence_path,
                "evidence_sha256": canonical_digest(observation),
                "failed_checks": observation["failed_checks"],
            },
            now=observed_at,
        )
        return {**result, "observation": observation}

    raise CloudAdvancementError(
        f"Executor {executor!r} is not safe for automatic execution."
    )


def observe_github_actions_gate(
    project_root: Path,
    program: Mapping[str, Any],
    *,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    runner = command_runner or _run_json_command
    gate = dict(program["hosted_ci_gate"])
    repository = str(gate["repository"])
    issue = dict(
        runner(
            [
                "gh",
                "issue",
                "view",
                str(gate["issue_number"]),
                "--repo",
                repository,
                "--json",
                "number,state,url,updatedAt",
            ],
            project_root.resolve(),
        )
    )
    pull_request = dict(
        runner(
            [
                "gh",
                "pr",
                "view",
                str(gate["pr_number"]),
                "--repo",
                repository,
                "--json",
                "headRefOid,url,statusCheckRollup",
            ],
            project_root.resolve(),
        )
    )
    check = _select_required_check(
        list(pull_request.get("statusCheckRollup", [])),
        str(gate["required_workflow"]),
        str(gate["required_job"]),
    )
    run_id = _run_id_from_details_url(str(check.get("detailsUrl", "")))
    run = dict(
        runner(
            [
                "gh",
                "run",
                "view",
                run_id,
                "--repo",
                repository,
                "--json",
                (
                    "databaseId,status,conclusion,headSha,workflowName,"
                    "jobs,url,updatedAt"
                ),
            ],
            project_root.resolve(),
        )
    )
    job = _select_required_job(
        list(run.get("jobs", [])),
        str(gate["required_job"]),
    )
    steps = list(job.get("steps", []))
    checks = {
        "issue_closed": str(issue.get("state", "")).upper() == "CLOSED",
        "pr_head_matches": (
            str(pull_request.get("headRefOid", ""))
            == str(gate["required_head_sha"])
        ),
        "run_head_matches": (
            str(run.get("headSha", ""))
            == str(gate["required_head_sha"])
        ),
        "workflow_matches": (
            str(run.get("workflowName", ""))
            == str(gate["required_workflow"])
        ),
        "run_succeeded": str(run.get("conclusion", "")).lower() == "success",
        "job_succeeded": str(job.get("conclusion", "")).lower() == "success",
        "job_has_executed_steps": len(steps) > 0,
    }
    failed_checks = sorted(
        key for key, passed in checks.items() if not passed
    )
    bounded_run = {
        "databaseId": int(run.get("databaseId", 0)),
        "status": str(run.get("status", "")),
        "conclusion": str(run.get("conclusion", "")),
        "headSha": str(run.get("headSha", "")),
        "workflowName": str(run.get("workflowName", "")),
        "url": str(run.get("url", "")),
        "updatedAt": str(run.get("updatedAt", "")),
    }
    return {
        "observer": "github_actions_gate",
        "repository": repository,
        "issue": {
            "number": int(issue.get("number", 0)),
            "state": str(issue.get("state", "")),
            "url": str(issue.get("url", "")),
            "updatedAt": str(issue.get("updatedAt", "")),
        },
        "pull_request": {
            "number": int(gate["pr_number"]),
            "headRefOid": str(pull_request.get("headRefOid", "")),
            "url": str(pull_request.get("url", "")),
        },
        "run": bounded_run,
        "job": {
            "name": str(job.get("name", "")),
            "status": str(job.get("status", "")),
            "conclusion": str(job.get("conclusion", "")),
            "url": str(job.get("url", "")),
        },
        "executed_step_count": len(steps),
        "checks": checks,
        "failed_checks": failed_checks,
        "gate_passed": not failed_checks,
        "provider_resource_mutation_performed": False,
        "credential_access_performed": False,
        "external_action_performed": False,
    }


def render_status_markdown(status: Mapping[str, Any]) -> str:
    lines = [
        "# AIGC Cloud Advancement Loop",
        "",
        f"Program: `{status['program_id']}`",
        f"Source revision: `{status['source_revision']}`",
        f"Source state: `{status['source_state']}`",
        (
            "Progress: "
            f"**{status['completed_action_count']} / "
            f"{status['total_action_count']} unique actions completed**"
        ),
        "",
        "## Actions",
        "",
        "| Stage | Action | State | Eligible | Reason |",
        "|---:|---|---|---:|---|",
    ]
    for item in status["action_results"]:
        lines.append(
            f"| {item['stage']} | `{item['action_id']}` "
            f"{item['title']} | {item['state']} | "
            f"{item['eligible']} | {item['eligibility_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- One action may be active per run.",
            "- Completed actions are never reselected.",
            "- Repetition is limited to recorded necessity after cooldown.",
            "- Direct main writes, automatic merge, Terraform apply, provider "
            "mutation, credential access, and external action remain disabled.",
        ]
    )
    return "\n".join(lines) + "\n"


def _baseline_evidence(
    project_root: Path,
    program: Mapping[str, Any],
    claim: Mapping[str, Any],
) -> dict[str, Any]:
    revision, source_state = repository_revision_state(project_root)
    action_fingerprints = {
        str(action["action_id"]): action_semantic_fingerprint(action)
        for action in program["actions"]
    }
    return {
        "evidence_type": "cloud_advancement_baseline",
        "program_id": program["program_id"],
        "program_digest": canonical_digest(program),
        "source_revision": revision,
        "source_state": source_state,
        "run_id": claim["run_id"],
        "action_count": len(program["actions"]),
        "action_fingerprints": action_fingerprints,
        "action_graph_digest": canonical_digest(
            [
                {
                    "action_id": action["action_id"],
                    "dependencies": action["dependencies"],
                }
                for action in program["actions"]
            ]
        ),
        "append_only_events": True,
        "completed_action_reselection_allowed": False,
        "max_actions_per_run": 1,
        "phase5_approval_present": False,
        "provider_resource_mutation_performed": False,
        "credential_access_performed": False,
        "external_action_performed": False,
    }


def _write_runtime_evidence(
    project_root: Path,
    program: Mapping[str, Any],
    run_id: str,
    filename: str,
    payload: Mapping[str, Any],
) -> str:
    root = project_root.resolve()
    evidence_root = _safe_runtime_path(
        root,
        Path(str(program["state"]["evidence_root"])),
        "cloud advancement evidence root",
    )
    path = evidence_root / run_id / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)
    return _relative_or_absolute(root, path)


def _run_json_command(
    command: Sequence[str],
    cwd: Path,
) -> Mapping[str, Any]:
    try:
        result = subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CloudAdvancementError(
            f"Read-only observation command could not run: {command[0]}."
        ) from exc
    if result.returncode != 0:
        bounded_error = result.stderr.strip()[:500]
        raise CloudAdvancementError(
            f"Read-only observation command failed: {bounded_error}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CloudAdvancementError(
            "Read-only observation command returned invalid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise CloudAdvancementError(
            "Read-only observation command must return a JSON object."
        )
    return payload


def _select_required_check(
    checks: Iterable[Mapping[str, Any]],
    workflow_name: str,
    job_name: str,
) -> dict[str, Any]:
    matching = [
        dict(check)
        for check in checks
        if str(check.get("workflowName", "")) == workflow_name
        and str(check.get("name", "")) == job_name
    ]
    if not matching:
        raise CloudAdvancementError(
            "The required hosted CI check is absent from the pull request."
        )
    return sorted(
        matching,
        key=lambda item: (
            str(item.get("completedAt", "")),
            str(item.get("startedAt", "")),
            str(item.get("detailsUrl", "")),
        ),
        reverse=True,
    )[0]


def _select_required_job(
    jobs: Iterable[Mapping[str, Any]],
    job_name: str,
) -> dict[str, Any]:
    matching = [
        dict(job)
        for job in jobs
        if str(job.get("name", "")) == job_name
    ]
    if not matching:
        raise CloudAdvancementError(
            "The required job is absent from the hosted workflow run."
        )
    return matching[0]


def _run_id_from_details_url(details_url: str) -> str:
    match = re.search(r"/actions/runs/([0-9]+)", details_url)
    if not match:
        raise CloudAdvancementError(
            "The required hosted CI check does not expose a workflow run ID."
        )
    return match.group(1)


def _strict_validate(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> None:
    Draft202012Validator.check_schema(dict(schema))
    validator = Draft202012Validator(
        dict(schema),
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(dict(payload)),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if not errors:
        return
    messages: list[str] = []
    for error in errors[:10]:
        location = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}"
            for part in error.absolute_path
        )
        messages.append(f"{location}: {error.message}")
    raise CloudAdvancementError(
        "Cloud advancement config validation failed: "
        + "; ".join(messages)
    )


def _assert_acyclic(
    action_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(action_id: str) -> None:
        if action_id in visited:
            return
        if action_id in visiting:
            raise CloudAdvancementError(
                "Cloud action dependency graph contains a cycle."
            )
        visiting.add(action_id)
        for dependency in action_by_id[action_id]["dependencies"]:
            visit(str(dependency))
        visiting.remove(action_id)
        visited.add(action_id)

    for action_id in action_by_id:
        visit(action_id)


def _assert_safe_evidence(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS:
                raise CloudAdvancementError(
                    f"Sensitive field {path}.{key} is prohibited in loop evidence."
                )
            _assert_safe_evidence(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_safe_evidence(item, f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                raise CloudAdvancementError(
                    f"Secret-like value is prohibited in loop evidence at {path}."
                )


def _normalize_text(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


def _safe_input_path(root: Path, value: Path, label: str) -> Path:
    path = (value if value.is_absolute() else root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise CloudAdvancementError(
            f"{label} must remain inside the AIGC workspace."
        ) from exc
    if not path.is_file():
        raise CloudAdvancementError(f"{label} must be an existing file.")
    return path


def _safe_runtime_path(root: Path, value: Path, label: str) -> Path:
    path = (value if value.is_absolute() else root / value).resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise CloudAdvancementError(
            f"{label} must remain inside the AIGC workspace."
        ) from exc
    if not relative.parts or relative.parts[0] != ".aigc":
        raise CloudAdvancementError(
            f"{label} must remain under the ignored .aigc runtime directory."
        )
    return path


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CloudAdvancementError(
            f"Invalid JSON at {path}: {exc.msg}."
        ) from exc
    if not isinstance(payload, dict):
        raise CloudAdvancementError(
            f"Expected a JSON object at {path}."
        )
    return payload


def _git_output(root: Path, arguments: Sequence[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _relative_or_absolute(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path.resolve())
