"""Tamper-evident policy receipts."""
from .canonicalization import sha256_digest
from .redaction import redact
def make_receipt(decision,repository,revision,bundle_digest):
    body={"receipt_id":f"PEL-{decision['decision_id']}","decision":redact(decision),"repository":repository,"exact_repository_revision":revision,"policy_bundle_digest":bundle_digest,"credential_material_included":False,"external_action_performed":False}
    body["receipt_sha256"]=sha256_digest(body)
    return body
def verify_receipt(receipt):
    body=dict(receipt); observed=body.pop("receipt_sha256",None)
    return isinstance(observed,str) and observed==sha256_digest(body)
