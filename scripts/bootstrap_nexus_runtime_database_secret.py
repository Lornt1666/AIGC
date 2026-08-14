from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
from typing import Any

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.api_core.client_options import ClientOptions
from google.cloud import secretmanager_v1
from psycopg.conninfo import make_conninfo

from scripts.aigc_external_release_procurement import ExternalReleaseContract, ProcurementError, discover
from scripts.provision_nexus_regional_secret_version import latest_exact_reference


REGION = "northamerica-northeast1"
USERNAME = "aigc_runtime"
DATABASE = "aigc_control"


class DatabaseBootstrapError(RuntimeError):
    pass


class DatabaseBootstrapPartial(DatabaseBootstrapError):
    pass


def _sql_session():
    credentials, _project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(credentials)


def _users(session: AuthorizedSession, *, project: str, instance: str) -> list[dict[str, Any]]:
    response = session.get(
        f"https://sqladmin.googleapis.com/sql/v1beta4/projects/{project}/instances/{instance}/users",
        timeout=30,
    )
    if response.status_code != 200:
        raise DatabaseBootstrapError(f"Cloud SQL user discovery failed with HTTP {response.status_code}")
    payload = response.json()
    items = payload.get("items") or []
    return [item for item in items if isinstance(item, dict)]


def _create_user(
    session: AuthorizedSession,
    *,
    project: str,
    instance: str,
    password: str,
) -> None:
    response = session.post(
        f"https://sqladmin.googleapis.com/sql/v1beta4/projects/{project}/instances/{instance}/users",
        json={"name": USERNAME, "password": password, "type": "BUILT_IN"},
        timeout=30,
    )
    if response.status_code not in {200, 201}:
        raise DatabaseBootstrapPartial(
            f"Cloud SQL runtime user creation failed with HTTP {response.status_code}"
        )


def _secret_client():
    return secretmanager_v1.SecretManagerServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"secretmanager.{REGION}.rep.googleapis.com"
        )
    )


def bootstrap(
    contract: ExternalReleaseContract,
    *,
    execute: bool,
    output: Path,
) -> dict[str, Any]:
    names = {
        "instance": f"{contract.prefix}-control",
        "secret": f"{contract.prefix}-runtime-control-dsn",
    }
    discovery = discover(contract)
    if not discovery["project_number_matches"] or not discovery["billing_link_matches"] or not discovery["billing_link_enabled"]:
        raise DatabaseBootstrapError("verified project/billing binding is required")
    if not discovery["cloud_sql_exists"]:
        raise DatabaseBootstrapError("Cloud SQL foundation is not present")
    existing_secret = latest_exact_reference(
        project=contract.project_id,
        secret_id=names["secret"],
    )

    session = _sql_session()
    existing_users = _users(
        session,
        project=contract.project_id,
        instance=names["instance"],
    )
    user_exists = any(str(item.get("name") or "") == USERNAME for item in existing_users)

    if existing_secret and user_exists:
        result = {
            "schema_version": "aigc.nexus-runtime-database-bootstrap-receipt.v1",
            "status": "existing_verified",
            "project_id": contract.project_id,
            "region": REGION,
            "cloud_sql_instance": names["instance"],
            "database": DATABASE,
            "runtime_user": USERNAME,
            "runtime_control_dsn_exact_version_ref": existing_secret,
            "cloud_mutation_performed": False,
            "secret_value_emitted": False,
            "reconciliation_required": False,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return result

    if existing_secret != user_exists:
        raise DatabaseBootstrapError(
            "runtime database credential state is partially provisioned; explicit reconciliation is required"
        )

    if not execute:
        return {
            "schema_version": "aigc.nexus-runtime-database-bootstrap-plan.v1",
            "project_id": contract.project_id,
            "region": REGION,
            "cloud_sql_instance": names["instance"],
            "database": DATABASE,
            "runtime_user": USERNAME,
            "regional_secret_id": names["secret"],
            "cloud_mutation_performed": False,
            "secret_value_emitted": False,
        }

    authority = contract.authority
    if authority.get("resource_creation_authorized") is not True:
        raise DatabaseBootstrapError("runtime database user creation is not authorized")
    if authority.get("secret_version_creation_authorized") is not True:
        raise DatabaseBootstrapError("runtime DSN secret-version creation is not authorized")
    if contract.payload.get("monthly_budget_cad", 0) <= 0:
        raise DatabaseBootstrapError("nonzero reviewed staging budget is required")

    password = secrets.token_urlsafe(36)
    connection_name = f"{contract.project_id}:{REGION}:{names['instance']}"
    dsn = make_conninfo(
        dbname=DATABASE,
        user=USERNAME,
        password=password,
        host=f"/cloudsql/{connection_name}",
    )
    parent = f"projects/{contract.project_id}/locations/{REGION}/secrets/{names['secret']}"
    secret_reference: str | None = None
    try:
        version = _secret_client().add_secret_version(
            request={"parent": parent, "payload": {"data": dsn.encode("utf-8")}}
        )
        secret_reference = str(version.name)
        _create_user(
            session,
            project=contract.project_id,
            instance=names["instance"],
            password=password,
        )
    except Exception as exc:
        result = {
            "schema_version": "aigc.nexus-runtime-database-bootstrap-receipt.v1",
            "status": "partial",
            "project_id": contract.project_id,
            "region": REGION,
            "cloud_sql_instance": names["instance"],
            "database": DATABASE,
            "runtime_user": USERNAME,
            "runtime_control_dsn_exact_version_ref": secret_reference,
            "cloud_mutation_performed": secret_reference is not None,
            "secret_value_emitted": False,
            "reconciliation_required": True,
            "failure_class": type(exc).__name__,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        raise DatabaseBootstrapPartial("database credential bootstrap became partial; do not retry blindly") from None
    finally:
        password = ""
        dsn = ""

    result = {
        "schema_version": "aigc.nexus-runtime-database-bootstrap-receipt.v1",
        "status": "succeeded",
        "project_id": contract.project_id,
        "region": REGION,
        "cloud_sql_instance": names["instance"],
        "database": DATABASE,
        "runtime_user": USERNAME,
        "runtime_control_dsn_exact_version_ref": secret_reference,
        "cloud_mutation_performed": True,
        "secret_value_emitted": False,
        "reconciliation_required": False,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--procurement", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = bootstrap(
        ExternalReleaseContract.load(args.procurement),
        execute=args.execute,
        output=args.output,
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProcurementError, DatabaseBootstrapError) as exc:
        raise SystemExit(f"Nexus runtime database bootstrap blocked: {exc}") from exc
