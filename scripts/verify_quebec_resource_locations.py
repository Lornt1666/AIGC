from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

QUEBEC = {
    "northamerica-northeast1",
    "NORTHAMERICA-NORTHEAST1",
}
CONTROL_PLANE_CLASSIFICATION = "CONTROL_PLANE_METADATA"
CONTROL_PLANE_STATUS = "VERIFIED_WITH_LIMITATION"


class RegionVerificationError(RuntimeError):
    pass


def digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def verify(payload: dict[str, Any]) -> dict[str, Any]:
    resources = payload.get("resources")
    if not isinstance(resources, list) or not resources:
        raise RegionVerificationError("customer-content resource inventory is required")

    non_quebec = []
    for item in resources:
        if not isinstance(item, dict):
            raise RegionVerificationError(
                "customer-content resource inventory item is invalid"
            )
        location = item.get("location")
        if location not in QUEBEC:
            non_quebec.append(
                {
                    "kind": item.get("kind"),
                    "name": item.get("name"),
                    "location": location,
                }
            )

    control_plane = payload.get("control_plane_resources")
    if not isinstance(control_plane, list) or not control_plane:
        raise RegionVerificationError(
            "global control-plane metadata inventory is required"
        )
    invalid_control_plane = []
    for item in control_plane:
        if not isinstance(item, dict):
            raise RegionVerificationError(
                "control-plane resource inventory item is invalid"
            )
        if (
            item.get("location") != "global"
            or item.get("classification") != CONTROL_PLANE_CLASSIFICATION
            or item.get("customer_content") is not False
            or item.get("residency_status") != CONTROL_PLANE_STATUS
        ):
            invalid_control_plane.append(
                {
                    "kind": item.get("kind"),
                    "name": item.get("name"),
                    "location": item.get("location"),
                    "classification": item.get("classification"),
                    "customer_content": item.get("customer_content"),
                    "residency_status": item.get("residency_status"),
                }
            )

    if payload.get("cross_region_replication") is not False:
        raise RegionVerificationError(
            "cross-region replication is not authorized"
        )
    if payload.get("public_resources") is not False:
        raise RegionVerificationError("public resources are not authorized")
    if payload.get("production_resources") is not False:
        raise RegionVerificationError("production resources are not authorized")
    if payload.get("service_account_keys") is not False:
        raise RegionVerificationError("service-account keys are prohibited")
    if payload.get("strict_quebec_data_residency_verified") is not False:
        raise RegionVerificationError(
            "strict Québec residency cannot be represented as verified while global control-plane metadata exists"
        )
    if non_quebec:
        raise RegionVerificationError(
            "non-Québec customer-content resources detected: "
            + json.dumps(non_quebec, sort_keys=True)
        )
    if invalid_control_plane:
        raise RegionVerificationError(
            "global control-plane metadata was not truthfully classified: "
            + json.dumps(invalid_control_plane, sort_keys=True)
        )

    return {
        "verified": True,
        "project_id": payload.get("project_id"),
        "customer_content_resource_count": len(resources),
        "global_control_plane_resource_count": len(control_plane),
        "non_quebec_customer_content_resources": [],
        "customer_content_quebec_region_verified": True,
        "strict_quebec_data_residency_verified": False,
        "silent_failover_outside_canada": False,
        "manifest_sha256": digest(payload),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RegionVerificationError("manifest must be an object")
    print(json.dumps(verify(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RegionVerificationError as exc:
        raise SystemExit(f"Québec resource verification blocked: {exc}") from exc
