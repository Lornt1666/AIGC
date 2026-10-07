from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping


class EvidenceLedgerError(ValueError):
    pass


@dataclass(frozen=True)
class LedgerEntry:
    sequence: int
    entry_id: str
    record: Mapping[str, object]
    previous_hash: str
    entry_hash: str

    def to_record(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "entry_id": self.entry_id,
            "record": dict(self.record),
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }


class EvidenceLedger:
    """Append-only, hash-chained evidence ledger with deterministic integrity checks.

    The ledger does not claim external persistence; callers own durable storage.
    """

    GENESIS = "GENESIS"

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._entries)

    def append(self, entry_id: str, record: Mapping[str, object]) -> LedgerEntry:
        if not entry_id:
            raise EvidenceLedgerError("entry_id is required.")
        if not isinstance(record, Mapping) or not record:
            raise EvidenceLedgerError("record must be a non-empty mapping.")
        if any(not isinstance(key, str) for key in record):
            raise EvidenceLedgerError("record keys must be strings.")

        sequence = len(self._entries) + 1
        previous_hash = self._entries[-1].entry_hash if self._entries else self.GENESIS
        payload = {
            "sequence": sequence,
            "entry_id": entry_id,
            "record": dict(record),
            "previous_hash": previous_hash,
        }
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        entry_hash = hashlib.sha256(canonical).hexdigest()
        entry = LedgerEntry(sequence, entry_id, dict(record), previous_hash, entry_hash)
        self._entries.append(entry)
        return entry

    def verify(self) -> bool:
        previous_hash = self.GENESIS
        for expected_sequence, entry in enumerate(self._entries, start=1):
            if entry.sequence != expected_sequence:
                return False
            if entry.previous_hash != previous_hash:
                return False
            payload = {
                "sequence": entry.sequence,
                "entry_id": entry.entry_id,
                "record": dict(entry.record),
                "previous_hash": entry.previous_hash,
            }
            canonical = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            if hashlib.sha256(canonical).hexdigest() != entry.entry_hash:
                return False
            previous_hash = entry.entry_hash
        return True

    def export_jsonl(self) -> str:
        if not self.verify():
            raise EvidenceLedgerError("Cannot export an invalid evidence ledger.")
        return "
".join(
            json.dumps(entry.to_record(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            for entry in self._entries
        )
