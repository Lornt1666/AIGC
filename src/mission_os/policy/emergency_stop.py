"""Consume emergency-stop evidence without owning state."""
def emergency_status(evidence,expected_epoch):
    if not evidence: return "UNKNOWN",["EMERGENCY_STOP_EVIDENCE_MISSING"]
    if evidence.get("epoch")!=expected_epoch: return "UNKNOWN",["EMERGENCY_STOP_EPOCH_MISMATCH"]
    if evidence.get("state")=="LOCKED": return "LOCKED",["EMERGENCY_STOP_LOCKED"]
    if evidence.get("state")=="UNLOCKED": return "UNLOCKED",[]
    return "UNKNOWN",["EMERGENCY_STOP_STATE_UNKNOWN"]
