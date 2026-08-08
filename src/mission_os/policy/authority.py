"""Consume Identity Kernel evidence without issuing authority."""
def authority_status(evidence):
    if not evidence: return False,["AUTHORITY_EVIDENCE_MISSING"]
    if evidence.get("decision")!="PERMIT": return False,["AUTHORITY_NOT_PERMITTED"]
    if evidence.get("expired") is True: return False,["AUTHORITY_EXPIRED"]
    if evidence.get("revoked") is True: return False,["AUTHORITY_REVOKED"]
    if not evidence.get("exact_repository_revision"): return False,["AUTHORITY_REVISION_MISSING"]
    return True,[]
