import json

import pytest

from src.core.omega_worker_evidence_ledger import EvidenceLedger, EvidenceLedgerError


def test_append_creates_hash_chained_entries():
    ledger = EvidenceLedger()
    first = ledger.append("e1", {"event": "SELECTED", "subject": "task-1"})
    second = ledger.append("e2", {"event": "VERIFIED", "subject": "task-1"})

    assert first.sequence == 1
    assert first.previous_hash == EvidenceLedger.GENESIS
    assert second.sequence == 2
    assert second.previous_hash == first.entry_hash
    assert first.entry_hash != second.entry_hash
    assert ledger.verify() is True


def test_export_is_canonical_jsonl():
    ledger = EvidenceLedger()
    ledger.append("e1", {"b": 2, "a": 1})
    exported = ledger.export_jsonl()
    record = json.loads(exported)
    assert list(record) == ["entry_hash", "entry_id", "previous_hash", "record", "sequence"]
    assert record["sequence"] == 1


def test_tampering_is_detected():
    ledger = EvidenceLedger()
    ledger.append("e1", {"event": "SELECTED"})
    ledger._entries[0] = ledger._entries[0].__class__(
        sequence=1,
        entry_id="e1",
        record={"event": "TAMPERED"},
        previous_hash=EvidenceLedger.GENESIS,
        entry_hash=ledger._entries[0].entry_hash,
    )
    assert ledger.verify() is False
    with pytest.raises(EvidenceLedgerError, match="invalid"):
        ledger.export_jsonl()


def test_invalid_input_is_rejected():
    ledger = EvidenceLedger()
    with pytest.raises(EvidenceLedgerError):
        ledger.append("", {"event": "x"})
    with pytest.raises(EvidenceLedgerError):
        ledger.append("e1", {})


def test_empty_ledger_is_valid_and_exports_empty_string():
    ledger = EvidenceLedger()
    assert ledger.verify() is True
    assert ledger.export_jsonl() == ""
