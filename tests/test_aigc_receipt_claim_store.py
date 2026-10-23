import unittest
from unittest.mock import patch

from aigc_runtime.receipt_claim_store import PostgresReceiptClaimStore, ReceiptClaimError


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.result = None
        self.last_params = None
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, query, params):
        self.last_params = params
        if query.lstrip().startswith("INSERT INTO aigc_receipt_claims"):
            receipt_id, digest, purpose, issuer, candidate = params
            if receipt_id not in self.state:
                self.state[receipt_id] = [digest, purpose, issuer, candidate, 1]
                self.result = (receipt_id,)
            else:
                self.result = None
        elif query.lstrip().startswith("SELECT payload_sha256"):
            row = self.state.get(params[0])
            self.result = tuple(row) if row else None
        elif query.lstrip().startswith("UPDATE aigc_receipt_claims"):
            self.state[params[0]][4] += 1
            self.result = None
    def fetchone(self): return self.result


class FakeConnection:
    def __init__(self, state): self.state = state
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def transaction(self): return self
    def cursor(self): return FakeCursor(self.state)


class ReceiptClaimStoreTests(unittest.TestCase):
    def test_dedicated_dsn_required(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ReceiptClaimError, "persistent_receipt_store_required"):
                PostgresReceiptClaimStore()

    def test_same_evidence_receipt_can_be_reobserved(self):
        state = {}
        store = PostgresReceiptClaimStore("postgresql://unused")
        payload = {"receipt_id": "R-1", "purpose": "human-acceptance", "issuer": "admin", "candidate_sha": "a"*40}
        verification = {"receipt_id": "R-1", "payload_digest": "sha256:" + "b"*64,
                        "purpose": "human-acceptance", "issuer": "admin"}
        with patch("aigc_runtime.receipt_claim_store.psycopg.connect", side_effect=lambda *a, **k: FakeConnection(state)):
            self.assertEqual(store.claim(payload, verification)["status"], "FIRST_OBSERVATION")
            self.assertEqual(store.claim(payload, verification)["status"], "SAME_EVIDENCE_REOBSERVED")

    def test_receipt_id_cannot_be_rebound_to_different_digest(self):
        state = {}
        store = PostgresReceiptClaimStore("postgresql://unused")
        payload = {"receipt_id": "R-1", "purpose": "human-acceptance", "issuer": "admin", "candidate_sha": "a"*40}
        first = {"receipt_id": "R-1", "payload_digest": "sha256:" + "b"*64,
                 "purpose": "human-acceptance", "issuer": "admin"}
        second = {**first, "payload_digest": "sha256:" + "c"*64}
        with patch("aigc_runtime.receipt_claim_store.psycopg.connect", side_effect=lambda *a, **k: FakeConnection(state)):
            store.claim(payload, first)
            with self.assertRaisesRegex(ReceiptClaimError, "different_claims"):
                store.claim(payload, second)

    def test_single_use_permit_replay_is_rejected(self):
        state = {}
        store = PostgresReceiptClaimStore("postgresql://unused")
        payload = {"receipt_id": "P-1", "purpose": "tool-permit", "issuer": "policy", "candidate_sha": "a"*40}
        verification = {"receipt_id": "P-1", "payload_digest": "sha256:" + "b"*64,
                        "purpose": "tool-permit", "issuer": "policy"}
        with patch("aigc_runtime.receipt_claim_store.psycopg.connect", side_effect=lambda *a, **k: FakeConnection(state)):
            store.claim(payload, verification)
            with self.assertRaisesRegex(ReceiptClaimError, "single_use_receipt_replayed"):
                store.claim(payload, verification)


if __name__ == "__main__":
    unittest.main()
