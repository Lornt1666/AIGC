from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from typing import Mapping
from .omega_worker_evidence_ledger import EvidenceLedger

class AdmissionLedgerError(ValueError):
    pass

@dataclass(frozen=True)
class AdmissionAuditReceipt:
    receipt_id: str
    policy_id: str
    connector_id: str
    evidence_reference: str
    evidence_id: str
    admitted: bool
    policy_fingerprint: str
    evidence_fingerprint: str
    ledger_entry_hash: str

class ConnectorAdmissionAuditLedger:
    """Creates tamper-evident admission receipts without granting authority."""
    def __init__(self, ledger: EvidenceLedger | None = None) -> None:
        self.ledger = ledger or EvidenceLedger()

    @staticmethod
    def _fingerprint(value: Mapping[str, object]) -> str:
        canonical = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        return hashlib.sha256(canonical).hexdigest()

    def record(self, *, receipt_id: str, policy_id: str, connector_id: str,
               evidence_reference: str, evidence_id: str, admitted: bool,
               policy: Mapping[str, object], evidence: Mapping[str, object]) -> AdmissionAuditReceipt:
        if any(not value for value in (receipt_id, policy_id, connector_id, evidence_reference, evidence_id)):
            raise AdmissionLedgerError("Admission receipt identity is incomplete.")
        if not isinstance(policy, Mapping) or not policy:
            raise AdmissionLedgerError("Admission policy evidence is required.")
        if not isinstance(evidence, Mapping) or not evidence:
            raise AdmissionLedgerError("Connector evidence is required.")
        pf, ef = self._fingerprint(policy), self._fingerprint(evidence)
        entry = self.ledger.append(f"admission:{receipt_id}", {
            "policy_id": policy_id, "connector_id": connector_id,
            "evidence_reference": evidence_reference, "evidence_id": evidence_id,
            "admitted": admitted, "policy_fingerprint": pf, "evidence_fingerprint": ef})
        return AdmissionAuditReceipt(receipt_id, policy_id, connector_id, evidence_reference,
                                     evidence_id, admitted, pf, ef, entry.entry_hash)

    def verify_receipt(self, receipt: AdmissionAuditReceipt) -> bool:
        for entry in self.ledger.entries:
            if entry.entry_id != f"admission:{receipt.receipt_id}":
                continue
            if entry.entry_hash != receipt.ledger_entry_hash:
                return False
            r = entry.record
            return (r.get("policy_id") == receipt.policy_id and
                    r.get("connector_id") == receipt.connector_id and
                    r.get("evidence_reference") == receipt.evidence_reference and
                    r.get("evidence_id") == receipt.evidence_id and
                    r.get("admitted") == receipt.admitted and
                    r.get("policy_fingerprint") == receipt.policy_fingerprint and
                    r.get("evidence_fingerprint") == receipt.evidence_fingerprint)
        return False

    def verify_chain(self) -> bool:
        return self.ledger.verify()
