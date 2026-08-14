from __future__ import annotations

import ast
import hashlib
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from .contracts import OutcomeContract, WorkAttempt, WorkCommission


class ScopeClassification(StrEnum):
    ADMITTED_DEPENDENCY = "ADMITTED_DEPENDENCY"
    FINDING = "FINDING"
    IMPROVEMENT_PROPOSAL = "IMPROVEMENT_PROPOSAL"
    BLOCKING_FINDING = "BLOCKING_FINDING"
    COMMISSION_AMENDMENT_PROPOSAL = "COMMISSION_AMENDMENT_PROPOSAL"


class MethodGenomeName(StrEnum):
    BUG_REPAIR = "BUG_REPAIR"
    FEATURE_IMPLEMENTATION = "FEATURE_IMPLEMENTATION"
    REPOSITORY_REFORMATION = "REPOSITORY_REFORMATION"
    ARCHITECTURE_MIGRATION = "ARCHITECTURE_MIGRATION"
    DEPENDENCY_MODERNIZATION = "DEPENDENCY_MODERNIZATION"
    TEST_HARDENING = "TEST_HARDENING"
    CI_REPAIR = "CI_REPAIR"
    SECURITY_HARDENING = "SECURITY_HARDENING"
    DOCUMENTATION_RECONSTRUCTION = "DOCUMENTATION_RECONSTRUCTION"
    OPERATIONALIZATION = "OPERATIONALIZATION"
    DEAD_CODE_ELIMINATION = "DEAD_CODE_ELIMINATION"
    RELEASE_PREPARATION = "RELEASE_PREPARATION"


class MethodGenome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    genome_id: str
    name: MethodGenomeName
    required_gates: tuple[str, ...]
    mutation_allowed: bool = True


DEFAULT_METHOD_GENOMES: tuple[MethodGenome, ...] = tuple(
    MethodGenome(
        genome_id=f"MG_{name.value}",
        name=name,
        required_gates=(
            "RepositoryMapped",
            "RequirementsBound",
            "ImpactAnalyzed",
            "WorkAttemptValid",
            "AuthorityValid",
        ),
    )
    for name in MethodGenomeName
)


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    target: str
    relation: str


class RepositoryAtlas(BaseModel):
    """Deterministic repository map produced before mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    root: str
    repository_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    file_graph: tuple[GraphEdge, ...]
    symbol_graph: tuple[GraphEdge, ...]
    import_graph: tuple[GraphEdge, ...]
    call_graph: tuple[GraphEdge, ...]
    test_coverage_graph: tuple[GraphEdge, ...]
    configuration_graph: tuple[GraphEdge, ...]
    build_graph: tuple[GraphEdge, ...]
    deployment_graph: tuple[GraphEdge, ...]
    data_flow_graph: tuple[GraphEdge, ...]
    authority_boundary_graph: tuple[GraphEdge, ...]
    evidence_graph: tuple[GraphEdge, ...]
    requirement_traceability_graph: tuple[GraphEdge, ...]
    parse_errors: tuple[str, ...] = ()

    @property
    def mapped(self) -> bool:
        return bool(self.repository_digest) and len(self.file_graph) >= 0


class WriteEligibility(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_mapped: bool
    requirements_bound: bool
    impact_analyzed: bool
    work_attempt_valid: bool
    authority_valid: bool

    @property
    def eligible(self) -> bool:
        return all(
            (
                self.repository_mapped,
                self.requirements_bound,
                self.impact_analyzed,
                self.work_attempt_valid,
                self.authority_valid,
            )
        )

    def require(self) -> None:
        if not self.eligible:
            failed = [
                name
                for name, value in (
                    ("RepositoryMapped", self.repository_mapped),
                    ("RequirementsBound", self.requirements_bound),
                    ("ImpactAnalyzed", self.impact_analyzed),
                    ("WorkAttemptValid", self.work_attempt_valid),
                    ("AuthorityValid", self.authority_valid),
                )
                if not value
            ]
            raise PermissionError("repository mutation denied; failed gates: " + ", ".join(failed))


class ScopeFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str
    classification: ScopeClassification
    rationale: str

    @property
    def may_enter_active_task_graph(self) -> bool:
        return self.classification is ScopeClassification.ADMITTED_DEPENDENCY


class RepositoryEngineer:
    """Bounded repository-engineering method runtime.

    Mapping and impact analysis are read-only. Mutation callers must explicitly
    pass the WRITE_ELIGIBLE gate; this class never infers broader scope from
    repository tidiness or unrelated findings.
    """

    CONFIG_NAMES = {
        "requirements.txt",
        "pyproject.toml",
        "setup.cfg",
        "tox.ini",
        "pytest.ini",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "Procfile",
    }

    DEPLOYMENT_PARTS = {".github", "terraform", "infra", "deploy", "k8s", "helm"}
    EVIDENCE_PARTS = {"evidence", "reports", "receipts", "audit"}
    AUTHORITY_TOKENS = {"authority", "authorization", "approval", "policy", "constitution", "mandate"}
    REQUIREMENT_TOKENS = {"requirement", "contract", "schema", "acceptance", "invariant"}

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def build_atlas(self) -> RepositoryAtlas:
        files = tuple(self._iter_files())
        file_edges: list[GraphEdge] = []
        symbol_edges: list[GraphEdge] = []
        import_edges: list[GraphEdge] = []
        call_edges: list[GraphEdge] = []
        test_edges: list[GraphEdge] = []
        config_edges: list[GraphEdge] = []
        build_edges: list[GraphEdge] = []
        deployment_edges: list[GraphEdge] = []
        data_edges: list[GraphEdge] = []
        authority_edges: list[GraphEdge] = []
        evidence_edges: list[GraphEdge] = []
        requirement_edges: list[GraphEdge] = []
        parse_errors: list[str] = []

        for path in files:
            rel = path.relative_to(self.root).as_posix()
            parent = path.parent.relative_to(self.root).as_posix() or "."
            file_edges.append(GraphEdge(source=parent, target=rel, relation="CONTAINS"))

            lower = rel.lower()
            if path.name in self.CONFIG_NAMES or path.suffix in {".toml", ".yaml", ".yml", ".ini"}:
                config_edges.append(GraphEdge(source=rel, target="CONFIGURATION", relation="CONFIGURES"))
            if any(part in self.DEPLOYMENT_PARTS for part in path.parts):
                deployment_edges.append(GraphEdge(source=rel, target="DEPLOYMENT_SURFACE", relation="PARTICIPATES_IN"))
            if path.name in {"Dockerfile", "Makefile"} or "build" in lower:
                build_edges.append(GraphEdge(source=rel, target="BUILD_SYSTEM", relation="PARTICIPATES_IN"))
            if any(token in lower for token in self.AUTHORITY_TOKENS):
                authority_edges.append(GraphEdge(source=rel, target="AUTHORITY_BOUNDARY", relation="DECLARES_OR_ENFORCES"))
            if any(part.lower() in self.EVIDENCE_PARTS for part in path.parts):
                evidence_edges.append(GraphEdge(source=rel, target="EVIDENCE_PLANE", relation="PRODUCES_OR_STORES"))
            if any(token in lower for token in self.REQUIREMENT_TOKENS):
                requirement_edges.append(GraphEdge(source=rel, target="REQUIREMENT_SYSTEM", relation="TRACES_TO"))
            if rel.startswith("tests/") or path.name.startswith("test_"):
                target = rel.removeprefix("tests/").replace("test_", "", 1)
                test_edges.append(GraphEdge(source=rel, target=target, relation="TESTS_APPROXIMATELY"))

            if path.suffix == ".py":
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
                except (SyntaxError, UnicodeDecodeError, OSError) as exc:
                    parse_errors.append(f"{rel}: {type(exc).__name__}: {exc}")
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        symbol_edges.append(GraphEdge(source=rel, target=node.name, relation="DEFINES"))
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            import_edges.append(GraphEdge(source=rel, target=alias.name, relation="IMPORTS"))
                    elif isinstance(node, ast.ImportFrom):
                        import_edges.append(GraphEdge(source=rel, target=node.module or "", relation="IMPORTS_FROM"))
                    elif isinstance(node, ast.Call):
                        called = self._call_name(node.func)
                        if called:
                            call_edges.append(GraphEdge(source=rel, target=called, relation="CALLS"))
                    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                        data_edges.append(GraphEdge(source=rel, target="LOCAL_STATE", relation="WRITES"))

        digest = self._repository_digest(files)
        return RepositoryAtlas(
            root=str(self.root),
            repository_digest=digest,
            file_graph=tuple(file_edges),
            symbol_graph=tuple(symbol_edges),
            import_graph=tuple(import_edges),
            call_graph=tuple(call_edges),
            test_coverage_graph=tuple(test_edges),
            configuration_graph=tuple(config_edges),
            build_graph=tuple(build_edges),
            deployment_graph=tuple(deployment_edges),
            data_flow_graph=tuple(data_edges),
            authority_boundary_graph=tuple(authority_edges),
            evidence_graph=tuple(evidence_edges),
            requirement_traceability_graph=tuple(requirement_edges),
            parse_errors=tuple(parse_errors),
        )

    def write_eligibility(
        self,
        *,
        atlas: RepositoryAtlas,
        commission: WorkCommission,
        outcome_contract: OutcomeContract,
        attempt: WorkAttempt,
        current_mandate_version: int,
        current_policy_version: str,
        impact_analyzed: bool,
        authority_valid: bool,
    ) -> WriteEligibility:
        attempt_valid = attempt.occupational_binding.matches(
            commission,
            outcome_contract,
            current_mandate_version=current_mandate_version,
            current_policy_version=current_policy_version,
        )
        requirements_bound = bool(commission.scope) and bool(outcome_contract.hard_gates)
        return WriteEligibility(
            repository_mapped=atlas.mapped,
            requirements_bound=requirements_bound,
            impact_analyzed=impact_analyzed,
            work_attempt_valid=attempt_valid,
            authority_valid=authority_valid,
        )

    @staticmethod
    def classify_discovery(
        description: str,
        *,
        required_for_current_outcome: bool = False,
        blocks_current_outcome: bool = False,
        requires_scope_expansion: bool = False,
        improvement_only: bool = False,
    ) -> ScopeFinding:
        if required_for_current_outcome:
            classification = ScopeClassification.ADMITTED_DEPENDENCY
            rationale = "required to satisfy the sealed OutcomeContract"
        elif blocks_current_outcome:
            classification = ScopeClassification.BLOCKING_FINDING
            rationale = "blocks current work but is not silently admitted as implementation scope"
        elif requires_scope_expansion:
            classification = ScopeClassification.COMMISSION_AMENDMENT_PROPOSAL
            rationale = "requires an upstream occupational amendment before implementation"
        elif improvement_only:
            classification = ScopeClassification.IMPROVEMENT_PROPOSAL
            rationale = "useful improvement outside the sealed commission"
        else:
            classification = ScopeClassification.FINDING
            rationale = "observed issue outside currently admitted task scope"
        return ScopeFinding(description=description, classification=classification, rationale=rationale)

    def _iter_files(self) -> Iterable[Path]:
        excluded = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in excluded for part in path.parts):
                continue
            yield path

    def _repository_digest(self, files: tuple[Path, ...]) -> str:
        digest = hashlib.sha256()
        for path in files:
            rel = path.relative_to(self.root).as_posix().encode("utf-8")
            digest.update(rel)
            digest.update(b"\0")
            try:
                digest.update(path.read_bytes())
            except OSError:
                digest.update(b"<unreadable>")
            digest.update(b"\0")
        return digest.hexdigest()

    @staticmethod
    def _call_name(node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parts: list[str] = []
            current: ast.expr = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts)) if parts else None
        return None
