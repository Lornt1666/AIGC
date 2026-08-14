from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PINNED_REQUIREMENT = re.compile(r"^[a-zA-Z0-9_.-]+==[^ \\]+(?: \\)?$")
IMMUTABLE_BASE_ARG = re.compile(
    r"^ARG PYTHON_BASE_IMAGE=(?P<image>[^\s]+@sha256:[a-f0-9]{64})$",
    re.MULTILINE,
)


class SupplyChainError(RuntimeError):
    pass


def verify(root: Path = ROOT) -> dict[str, object]:
    lock_path = root / "requirements.lock"
    lock_lines = lock_path.read_text(encoding="utf-8").splitlines()
    package_indexes = [
        index for index, line in enumerate(lock_lines)
        if PINNED_REQUIREMENT.fullmatch(line)
    ]
    if not package_indexes:
        raise SupplyChainError("requirements.lock contains no exact package pins")
    for position, start in enumerate(package_indexes):
        stop = (
            package_indexes[position + 1]
            if position + 1 < len(package_indexes)
            else len(lock_lines)
        )
        if not any("--hash=sha256:" in line for line in lock_lines[start:stop]):
            raise SupplyChainError(
                f"hash is missing for locked requirement at line {start + 1}"
            )

    dockerfile = (root / "Dockerfile.nexus").read_text(encoding="utf-8")
    for required in (
        "COPY requirements.lock",
        "--require-hashes",
        "python -m pip check",
        "ARG PYTHON_BASE_IMAGE",
        "org.opencontainers.image.revision",
        "ai.aigc.source-context-sha256",
    ):
        if required not in dockerfile:
            raise SupplyChainError(f"Dockerfile is missing {required}")
    if "pip install --no-cache-dir --upgrade pip" in dockerfile:
        raise SupplyChainError("Dockerfile performs an unbounded pip upgrade")
    base_match = IMMUTABLE_BASE_ARG.search(dockerfile)
    if base_match is None:
        raise SupplyChainError("Dockerfile default Python base image is not immutable")

    cloudbuild = (root / "cloudbuild.nexus.yaml").read_text(encoding="utf-8")
    for required in (
        "${_DOCKER_BUILDER_IMAGE}",
        "PYTHON_BASE_IMAGE=${_PYTHON_BASE_IMAGE}",
        "RELEASE_SHA=${_RELEASE_SHA}",
        "SOURCE_CONTEXT_SHA256=${_SOURCE_CONTEXT_SHA256}",
        "--platform=linux/amd64",
        "requestedVerifyOption: VERIFIED",
    ):
        if required not in cloudbuild:
            raise SupplyChainError(f"Cloud Build is missing {required}")

    allowlist = json.loads(
        (root / "config/nexus_build_context_allowlist.json").read_text(
            encoding="utf-8"
        )
    )
    required_files = set(allowlist.get("required_files") or [])
    for required in (
        "Dockerfile.nexus",
        "cloudbuild.nexus.yaml",
        "requirements.lock",
        "migrations/003_nexus_provider_runtime_controls.sql",
        "migrations/004_nexus_persisted_authority.sql",
    ):
        if required not in required_files:
            raise SupplyChainError(f"build-context allowlist is missing {required}")
    if allowlist.get("required_prefixes") != ["src/"]:
        raise SupplyChainError("build-context prefix set must be exactly src/")

    return {
        "schema_version": "aigc.nexus-supply-chain-verification.v1",
        "locked_package_count": len(package_indexes),
        "all_dependencies_hashed": True,
        "build_inputs_allowlisted": True,
        "cloud_builder_requires_immutable_substitution": True,
        "base_image_requires_reviewed_substitution_for_cloud_build": True,
        "immutable_local_ci_base_image": base_match.group("image"),
        "external_action_performed": False,
    }


def main() -> int:
    print(json.dumps(verify(), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SupplyChainError as exc:
        raise SystemExit(f"Nexus supply chain blocked: {exc}") from exc
