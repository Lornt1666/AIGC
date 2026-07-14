from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACK_PATH = ROOT / "config" / "staging_identity_procurement_readiness_pack.json"
DEFAULT_PACK_SCHEMA = ROOT / "schemas" / "staging_identity_procurement_readiness_pack.schema.json"
DEFAULT_PLAN_AUTH_SCHEMA = ROOT / "schemas" / "staging_identity_plan_authorization_receipt.schema.json"
DEFAULT_PLAN_EVIDENCE_SCHEMA = ROOT / "schemas" / "staging_identity_plan_evidence_receipt.schema.json"
DEFAULT_APPLY_AUTH_SCHEMA = ROOT / "schemas" / "staging_identity_apply_authorization_receipt.schema.json"
DEFAULT_EVALUATION_SCHEMA = ROOT / "schemas" / "staging_identity_procurement_evaluation.schema.json"
_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_REQUIRED_APIS = {
    "cloudresourcemanager.googleapis.com", "iam.googleapis.com",
    "iamcredentials.googleapis.com", "identitytoolkit.googleapis.com",
    "secretmanager.googleapis.com", "serviceusage.googleapis.com",
    "storage.googleapis.com", "sts.googleapis.com",
}

class StagingIdentityProcurementError(ValueError):
    """Raised when a procurement artifact violates its contract."""

@dataclass(frozen=True)
class StagingIdentityProcurementEvaluation:
    receipt: dict[str, Any]
    procurement_pack: dict[str, Any]
    @property
    def pack_ready(self) -> bool: return bool(self.receipt["pack_ready_for_plan_review"])
    @property
    def plan_authorization_effective(self) -> bool: return bool(self.receipt["plan_authorization_effective"])
    @property
    def plan_evidence_accepted(self) -> bool: return bool(self.receipt["plan_evidence_accepted"])
    @property
    def apply_authorization_effective(self) -> bool: return bool(self.receipt["apply_authorization_effective"])

def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

def canonical_digest(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode()).hexdigest()

def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def _parse_time(value: object, label: str) -> datetime:
    try: return _utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError as exc: raise StagingIdentityProcurementError(f"{label} is invalid") from exc

def _validate(path: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    try: schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise StagingIdentityProcurementError(f"Unable to load schema: {path.name}") from exc
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(dict(value)), key=lambda e: list(e.absolute_path))
    if errors:
        messages=[]
        for error in errors[:10]:
            location="$"+"".join(f"[{p}]" if isinstance(p,int) else f".{p}" for p in error.absolute_path)
            messages.append(f"{location}: {error.message}")
        raise StagingIdentityProcurementError(f"{path.name} validation failed: {'; '.join(messages)}")
    return dict(value)

def load_procurement_pack(path: str | Path = DEFAULT_PACK_PATH) -> dict[str, Any]:
    try: value=json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise StagingIdentityProcurementError("Unable to load staging identity procurement pack") from exc
    if not isinstance(value, dict): raise StagingIdentityProcurementError("Procurement pack must be an object")
    return _validate(DEFAULT_PACK_SCHEMA, value)

def _project(value: str, prefix: str) -> str:
    return value.removeprefix(prefix).split("/",1)[0]

def _time_reasons(receipt: Mapping[str, Any], now: datetime, hours: int, prefix: str) -> list[str]:
    issued=_parse_time(receipt["issued_at"], f"{prefix} issued_at")
    expires=_parse_time(receipt["expires_at"], f"{prefix} expires_at")
    out=[]
    if expires<=issued: out.append(f"{prefix}_LIFETIME_INVALID")
    if issued>now: out.append(f"{prefix}_FUTURE_DATED")
    if now>=expires: out.append(f"{prefix}_EXPIRED")
    if (expires-issued).total_seconds()>hours*3600: out.append(f"{prefix}_TTL_EXCEEDED")
    return out

def _pack_reasons(pack: Mapping[str, Any], revision: str, now: datetime) -> list[str]:
    out=[]
    if pack.get("artifact_kind")!="SUBMISSION": out.append("PROCUREMENT_PACK_TEMPLATE_NOT_SUBMISSION")
    if pack.get("status")!="READY_FOR_PLAN_REVIEW": out.append("PROCUREMENT_PACK_NOT_READY")
    if pack.get("unresolved_requirements")!=[]: out.append("PROCUREMENT_REQUIREMENTS_UNRESOLVED")
    if revision=="unbound": out.append("REVISION_UNBOUND")
    life=dict(pack.get("lifecycle") or {})
    if life.get("created_at") is None or life.get("expires_at") is None: out.append("PROCUREMENT_PACK_LIFETIME_UNBOUND")
    else:
        created=_parse_time(life["created_at"],"procurement created_at"); expires=_parse_time(life["expires_at"],"procurement expires_at")
        if expires<=created: out.append("PROCUREMENT_PACK_LIFETIME_INVALID")
        if created>now: out.append("PROCUREMENT_PACK_FUTURE_DATED")
        if now>=expires: out.append("PROCUREMENT_PACK_EXPIRED")
        if (expires-created).total_seconds()>7*86400: out.append("PROCUREMENT_PACK_TTL_EXCEEDED")
    if life.get("revoked") is True: out.append("PROCUREMENT_PACK_REVOKED")
    project=dict(pack.get("project") or {}); workload=dict(pack.get("workload_identity") or {})
    provider=dict(pack.get("identity_platform_google_provider") or {}); session=dict(pack.get("session_security") or {})
    state=dict(pack.get("terraform_state") or {}); iam=dict(pack.get("iam_separation") or {})
    pid=str(project.get("project_id") or ""); pref=str(project.get("project_reference") or ""); pnum=str(project.get("project_number") or "")
    if pref and pid and _project(pref,"gcp_project://")!=pid: out.append("PROJECT_REFERENCE_ID_MISMATCH")
    if not _REQUIRED_APIS.issubset(set(project.get("enabled_api_service_names") or [])): out.append("REQUIRED_APIS_NOT_VERIFIED")
    pool=str(workload.get("pool_resource_name") or ""); prov=str(workload.get("provider_resource_name") or "")
    if pnum and pool and f"/projects/{pnum}/" not in pool: out.append("WIF_POOL_PROJECT_NUMBER_MISMATCH")
    if pnum and prov and f"/projects/{pnum}/" not in prov: out.append("WIF_PROVIDER_PROJECT_NUMBER_MISMATCH")
    if pool and prov and not prov.startswith(pool.replace("gcp_wif_pool://","gcp_wif_provider://")+"/providers/"): out.append("WIF_PROVIDER_POOL_MISMATCH")
    accounts=[str(workload.get(k) or "") for k in ("plan_service_account_reference","apply_service_account_reference","application_runtime_service_account_reference")]
    if all(accounts):
        if len(set(accounts))!=3: out.append("IAM_IDENTITIES_NOT_DISTINCT")
        if pid and any(_project(v,"gcp_service_account://")!=pid for v in accounts): out.append("SERVICE_ACCOUNT_PROJECT_MISMATCH")
    secrets=[str(provider.get("google_oauth_web_client_secret_reference") or ""),str(session.get("session_pepper_secret_reference") or "")]
    if all(secrets) and secrets[0]==secrets[1]: out.append("OAUTH_AND_SESSION_SECRET_NOT_SEPARATE")
    if pid and any(v and _project(v,"gcp_secret://")!=pid for v in secrets): out.append("SECRET_REFERENCE_PROJECT_MISMATCH")
    state_refs=[str(state.get("bucket_reference") or ""),str(state.get("state_reference") or "")]
    if pid and any(v and _project(v,v.split("://",1)[0]+"://")!=pid for v in state_refs): out.append("STATE_REFERENCE_PROJECT_MISMATCH")
    domain=str(provider.get("authorized_domain") or "").removeprefix("dns_name://").lower()
    if domain and any((urlparse(str(provider.get(k) or "")).hostname or "").lower()!=domain for k in ("authorized_origin","authorized_redirect_uri")): out.append("AUTHORIZED_DOMAIN_ORIGIN_REDIRECT_MISMATCH")
    if iam.get("bootstrap_administrator_separate") is not True: out.append("BOOTSTRAP_ADMINISTRATOR_NOT_SEPARATE")
    if iam.get("plan_apply_runtime_identities_distinct") is not True: out.append("PLAN_APPLY_RUNTIME_IDENTITIES_NOT_ATTESTED_DISTINCT")
    phase=pack.get("requested_plan_phase")
    if phase=="STATE_BACKEND_BOOTSTRAP" and state.get("bootstrap_status")!="READY_FOR_BOOTSTRAP_PLAN": out.append("STATE_BACKEND_NOT_READY_FOR_BOOTSTRAP_PLAN")
    elif phase=="STAGING_IDENTITY_CONFIGURATION":
        required={"bootstrap_status":"BOOTSTRAPPED_VERIFIED","bucket_preexists_backend_init_attestation":"VERIFIED_TRUE","uniform_bucket_level_access_attestation":"VERIFIED_TRUE","public_access_prevention_attestation":"VERIFIED_TRUE","object_versioning_attestation":"VERIFIED_TRUE","state_locking_attestation":"VERIFIED_TRUE"}
        if any(state.get(k)!=v for k,v in required.items()): out.append("STATE_BACKEND_NOT_VERIFIED_FOR_IDENTITY_PLAN")
        if not state.get("rollback_generation_reference"): out.append("STATE_ROLLBACK_GENERATION_UNBOUND")
    elif phase not in {"STATE_BACKEND_BOOTSTRAP","STAGING_IDENTITY_CONFIGURATION"}: out.append("PROCUREMENT_PLAN_PHASE_UNBOUND")
    return list(dict.fromkeys(out))

def evaluate_staging_identity_procurement(*, procurement_pack: Mapping[str, Any], exact_revision: str | None, plan_authorization_receipt: Mapping[str, Any] | None=None, plan_evidence_receipt: Mapping[str, Any] | None=None, apply_authorization_receipt: Mapping[str, Any] | None=None, now: datetime | None=None) -> StagingIdentityProcurementEvaluation:
    pack=_validate(DEFAULT_PACK_SCHEMA,procurement_pack); current=_utc(now or datetime.now(timezone.utc)); revision=str(exact_revision) if exact_revision and _HEX40.fullmatch(str(exact_revision)) else "unbound"; digest=canonical_digest(pack)
    pack_reasons=_pack_reasons(pack,revision,current); pack_ready=not pack_reasons
    plan_reasons=[]; plan=None
    if plan_authorization_receipt is None: plan_reasons.append("PLAN_AUTHORIZATION_RECEIPT_MISSING")
    else:
        try: plan=_validate(DEFAULT_PLAN_AUTH_SCHEMA,plan_authorization_receipt)
        except StagingIdentityProcurementError: plan_reasons.append("PLAN_AUTHORIZATION_RECEIPT_INVALID")
        else:
            if not pack_ready: plan_reasons.append("PROCUREMENT_PACK_NOT_EFFECTIVE")
            if plan["exact_revision"]!=revision: plan_reasons.append("PLAN_AUTHORIZATION_REVISION_MISMATCH")
            if plan["procurement_pack_digest"]!=digest: plan_reasons.append("PLAN_AUTHORIZATION_PACK_DIGEST_MISMATCH")
            if plan["phase"]!=pack.get("requested_plan_phase"): plan_reasons.append("PLAN_AUTHORIZATION_PHASE_MISMATCH")
            if plan["target_project_reference"]!=pack["project"]["project_reference"]: plan_reasons.append("PLAN_AUTHORIZATION_PROJECT_MISMATCH")
            if plan["decision"]!="APPROVED": plan_reasons.append("PLAN_AUTHORIZATION_OPERATOR_DENIED")
            plan_reasons += _time_reasons(plan,current,4,"PLAN_AUTHORIZATION_RECEIPT")
    plan_reasons=list(dict.fromkeys(plan_reasons)); plan_effective=plan is not None and not plan_reasons
    ev_reasons=[]; evidence=None
    if plan_evidence_receipt is None: ev_reasons.append("PLAN_EVIDENCE_RECEIPT_MISSING")
    else:
        try: evidence=_validate(DEFAULT_PLAN_EVIDENCE_SCHEMA,plan_evidence_receipt)
        except StagingIdentityProcurementError: ev_reasons.append("PLAN_EVIDENCE_RECEIPT_INVALID")
        else:
            if not plan_effective: ev_reasons.append("PLAN_AUTHORIZATION_NOT_EFFECTIVE")
            checks=(("exact_revision",revision,"PLAN_EVIDENCE_REVISION_MISMATCH"),("procurement_pack_digest",digest,"PLAN_EVIDENCE_PACK_DIGEST_MISMATCH"),("phase",pack.get("requested_plan_phase"),"PLAN_EVIDENCE_PHASE_MISMATCH"),("target_project_reference",pack["project"]["project_reference"],"PLAN_EVIDENCE_PROJECT_MISMATCH"))
            for key,expected,code in checks:
                if evidence[key]!=expected: ev_reasons.append(code)
            if plan and evidence["plan_authorization_receipt_id"]!=plan["receipt_id"]: ev_reasons.append("PLAN_EVIDENCE_AUTHORIZATION_MISMATCH")
            if evidence["plan_result"]!="SUCCESS": ev_reasons.append("PLAN_EVIDENCE_FAILED")
            if evidence["review_status"]!="ACCEPTED": ev_reasons.append("PLAN_EVIDENCE_NOT_ACCEPTED")
    ev_reasons=list(dict.fromkeys(ev_reasons)); evidence_ok=evidence is not None and not ev_reasons
    apply_reasons=[]; apply=None
    if apply_authorization_receipt is None: apply_reasons.append("APPLY_AUTHORIZATION_RECEIPT_MISSING")
    else:
        try: apply=_validate(DEFAULT_APPLY_AUTH_SCHEMA,apply_authorization_receipt)
        except StagingIdentityProcurementError: apply_reasons.append("APPLY_AUTHORIZATION_RECEIPT_INVALID")
        else:
            if not pack_ready: apply_reasons.append("PROCUREMENT_PACK_NOT_EFFECTIVE")
            if not evidence_ok: apply_reasons.append("PLAN_EVIDENCE_NOT_EFFECTIVE")
            checks=(("exact_revision",revision,"APPLY_AUTHORIZATION_REVISION_MISMATCH"),("procurement_pack_digest",digest,"APPLY_AUTHORIZATION_PACK_DIGEST_MISMATCH"),("phase",pack.get("requested_plan_phase"),"APPLY_AUTHORIZATION_PHASE_MISMATCH"),("target_project_reference",pack["project"]["project_reference"],"APPLY_AUTHORIZATION_PROJECT_MISMATCH"))
            for key,expected,code in checks:
                if apply[key]!=expected: apply_reasons.append(code)
            if apply["decision"]!="APPROVED": apply_reasons.append("APPLY_AUTHORIZATION_OPERATOR_DENIED")
            if evidence:
                comparisons=(("plan_evidence_receipt_id",evidence["receipt_id"],"APPLY_AUTHORIZATION_PLAN_EVIDENCE_ID_MISMATCH"),("plan_evidence_digest",canonical_digest(evidence),"APPLY_AUTHORIZATION_PLAN_EVIDENCE_DIGEST_MISMATCH"),("plan_artifact_digest",evidence["plan_artifact_digest"],"APPLY_AUTHORIZATION_PLAN_ARTIFACT_MISMATCH"),("planned_resources",evidence["planned_resources"],"APPLY_AUTHORIZATION_RESOURCE_LIST_MISMATCH"),("planned_iam_delta",evidence["planned_iam_delta"],"APPLY_AUTHORIZATION_IAM_DELTA_MISMATCH"))
                for key,expected,code in comparisons:
                    if apply[key]!=expected: apply_reasons.append(code)
            provider=pack["identity_platform_google_provider"]
            if apply["authorized_origins"]!=[provider["authorized_origin"]]: apply_reasons.append("APPLY_AUTHORIZATION_ORIGIN_MISMATCH")
            if apply["authorized_redirect_uris"]!=[provider["authorized_redirect_uri"]]: apply_reasons.append("APPLY_AUTHORIZATION_REDIRECT_MISMATCH")
            expected_secrets=sorted([provider["google_oauth_web_client_secret_reference"],pack["session_security"]["session_pepper_secret_reference"]])
            if sorted(apply["secret_references"])!=expected_secrets: apply_reasons.append("APPLY_AUTHORIZATION_SECRET_REFERENCE_MISMATCH")
            apply_reasons += _time_reasons(apply,current,1,"APPLY_AUTHORIZATION_RECEIPT")
    apply_reasons=list(dict.fromkeys(apply_reasons)); apply_effective=apply is not None and not apply_reasons
    material="|".join([revision,digest,",".join(pack_reasons),",".join(plan_reasons),",".join(ev_reasons),",".join(apply_reasons)])
    receipt={"contract_id":"AIGC-STAGING-IDENTITY-PROCUREMENT-EVALUATION-001","contract_version":"1.0.0","evaluation_id":"SIPE-"+sha256(material.encode()).hexdigest()[:24].upper(),"exact_revision":revision,"procurement_pack_digest":digest,"pack_artifact_kind":pack["artifact_kind"],"pack_status":pack["status"],"pack_ready_for_plan_review":pack_ready,"pack_reason_codes":pack_reasons,"plan_authorization_receipt_present":plan_authorization_receipt is not None,"plan_authorization_effective":plan_effective,"plan_authorization_reason_codes":plan_reasons,"plan_evidence_receipt_present":plan_evidence_receipt is not None,"plan_evidence_accepted":evidence_ok,"plan_evidence_reason_codes":ev_reasons,"apply_authorization_receipt_present":apply_authorization_receipt is not None,"apply_authorization_effective":apply_effective,"apply_authorization_reason_codes":apply_reasons,"evaluated_at":current.isoformat(),"authorization_receipt_issued_by_evaluator":False,"provider_action_performed":False,"terraform_plan_performed":False,"terraform_apply_performed":False,"operator_review_required":True,"automatic_apply_allowed":False,"external_action_performed":False}
    return StagingIdentityProcurementEvaluation(_validate(DEFAULT_EVALUATION_SCHEMA,receipt),pack)
