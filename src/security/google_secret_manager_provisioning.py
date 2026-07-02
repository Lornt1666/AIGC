from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class GCloudSecretCommandPlan:
    project_id: str
    member: str
    commands: List[str]
    warnings: List[str]
    external_action_performed: bool = False


class GoogleSecretManagerProvisioningPlanner:
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def build_plan(self, project_id: str, member: str) -> GCloudSecretCommandPlan:
        commands = [
            f"gcloud config set project {project_id}",
            "gcloud services enable secretmanager.googleapis.com",
        ]
        warnings = [
            "This plan does not execute commands.",
            "Do not paste real secret values into chat, prompts, source files, audit logs, or manifests.",
            "Avoid long-lived downloaded service account key JSON files when possible.",
            "Use Google Cloud KMS for cryptographic encryption keys, not for general API-key/password storage.",
        ]
        for secret_key, record in (self.manifest.get("secrets", {}) or {}).items():
            if secret_key == "FAKE_TEST_SECRET":
                continue
            resource = str(record.get("resource", ""))
            secret_id = self._secret_id_from_resource(resource)
            if not secret_id:
                warnings.append(f"{secret_key}: could not infer secret id from resource {resource}")
                continue
            commands.extend([
                f"gcloud secrets create {secret_id} --replication-policy=\"automatic\"",
                f"gcloud secrets versions add {secret_id} --data-file=-",
                f"gcloud secrets add-iam-policy-binding {secret_id} --member=\"{member}\" --role=\"roles/secretmanager.secretAccessor\"",
            ])
        return GCloudSecretCommandPlan(
            project_id=project_id,
            member=member,
            commands=commands,
            warnings=warnings,
            external_action_performed=False,
        )

    def _secret_id_from_resource(self, resource: str) -> str:
        parts = resource.split("/")
        try:
            index = parts.index("secrets")
        except ValueError:
            return ""
        if index + 1 >= len(parts):
            return ""
        return parts[index + 1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a non-executing Google Secret Manager command plan.")
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "config" / "secret_manifest.json")
    parser.add_argument("--project-id", default="YOUR_PROJECT_ID")
    parser.add_argument("--member", default="user:YOUR_EMAIL@example.com")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "phase11_security" / "google_secret_manager_command_plan.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planner = GoogleSecretManagerProvisioningPlanner(args.manifest)
    plan = planner.build_plan(project_id=args.project_id, member=args.member)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(plan), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(asdict(plan), indent=2))
    print(f"Plan exported: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
