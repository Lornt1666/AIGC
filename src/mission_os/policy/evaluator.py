"""Deterministic fail-closed evaluator."""
from datetime import datetime
from .authority import authority_status
from .canonicalization import sha256_digest
from .emergency_stop import emergency_status
from .redaction import contains_secret
def _parse(ts): return datetime.fromisoformat(ts.replace("Z","+00:00"))
def evaluate(request,bundle,*,expected_repository,expected_revision,known_surfaces,authority_evidence,emergency_evidence,consumed_idempotency_keys=None):
    consumed_idempotency_keys=consumed_idempotency_keys or set()
    reasons=[]; blocking=[]; evaluated=[]
    required={"request_id","repository","exact_repository_revision","execution_surface","action_class","policy_version","policy_bundle_digest","emergency_stop_epoch","idempotency_key","issued_at","expires_at"}
    reasons.extend(f"MISSING_{x.upper()}" for x in sorted(required-request.keys()))
    if request.get("policy_bundle_digest")!=bundle.get("bundle_sha256"): reasons.append("POLICY_BUNDLE_DIGEST_MISMATCH")
    if request.get("repository")!=expected_repository: reasons.append("REPOSITORY_MISMATCH")
    if request.get("exact_repository_revision")!=expected_revision: reasons.append("REVISION_MISMATCH")
    if request.get("execution_surface") not in known_surfaces: reasons.append("UNKNOWN_EXECUTION_SURFACE")
    if request.get("idempotency_key") in consumed_idempotency_keys: reasons.append("REPLAY_DETECTED")
    try:
        if _parse(request["expires_at"])<=_parse(request["issued_at"]): reasons.append("INVALID_EXPIRY")
    except Exception: reasons.append("INVALID_TIME")
    emergency_state,emergency_reasons=emergency_status(emergency_evidence,int(request.get("emergency_stop_epoch",-1)))
    if emergency_state=="LOCKED":
        decision="EMERGENCY_STOP_LOCKED"; reasons.extend(emergency_reasons)
    elif emergency_state=="UNKNOWN":
        decision="INSUFFICIENT_EVIDENCE"; reasons.extend(emergency_reasons)
    else:
        ok,auth_reasons=authority_status(authority_evidence)
        if not ok:
            decision="INSUFFICIENT_EVIDENCE"; reasons.extend(auth_reasons)
        elif reasons:
            decision="DENY"
        else:
            action=request.get("action_class")
            matching=sorted([r for r in bundle.get("rules",[]) if r.get("active") and action in r.get("action_classes",[])],key=lambda r:(-int(r.get("priority",0)),r.get("rule_id","")))
            evaluated=[r["rule_id"] for r in matching]
            deny=[r for r in matching if r["effect"]=="DENY"]; approval=[r for r in matching if r["effect"]=="ALLOW_WITH_APPROVAL"]; allow=[r for r in matching if r["effect"]=="ALLOW"]
            if deny:
                decision="DENY"; blocking=[r["rule_id"] for r in deny]; reasons.extend(r["reason_code"] for r in deny)
            elif contains_secret(request):
                decision="DENY"; reasons.append("SECRET_MATERIAL_PRESENT")
            elif approval:
                ref=request.get("approval_reference")
                if not ref: decision="ALLOW_WITH_APPROVAL"; reasons.append("APPROVAL_REQUIRED")
                elif ref.get("approver")==request.get("actor_reference",{}).get("actor_id"): decision="DENY"; reasons.append("SELF_APPROVAL_PROHIBITED")
                elif ref.get("expired") is True: decision="DENY"; reasons.append("APPROVAL_EXPIRED")
                else: decision="ALLOW"; reasons.append("APPROVAL_SATISFIED")
            elif allow:
                decision="ALLOW"; reasons.extend(r["reason_code"] for r in allow)
            else:
                decision=bundle.get("default_decision","DENY"); reasons.append("DEFAULT_DENY")
    core={"decision_id":request.get("request_id","UNKNOWN"),"request_id":request.get("request_id","UNKNOWN"),"policy_version":bundle.get("version","UNKNOWN"),"policy_bundle_digest":bundle.get("bundle_sha256",""),"exact_repository_revision":request.get("exact_repository_revision",""),"evaluated_rule_ids":evaluated,"decision":decision,"authority_evidence":[] if authority_evidence is None else ["IDENTITY_KERNEL_GATE_RECEIPT"],"approval_evidence":[] if not request.get("approval_reference") else ["APPROVAL_REFERENCE"],"emergency_stop_state":emergency_state,"reasons":sorted(set(reasons)),"blocking_rules":sorted(set(blocking)),"issued_at":request.get("issued_at",""),"expires_at":request.get("expires_at","")}
    core["deterministic_digest"]=sha256_digest(core)
    return core
