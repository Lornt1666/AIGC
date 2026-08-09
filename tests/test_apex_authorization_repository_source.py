from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from src.apex_completion.authorization_reconstruction import reconstruct_authorization_register


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "phase5_authorizations" / "aigc_phase5_authorization_packets.json"
AS_OF = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)


def test_repository_phase5_source_is_historical_evidence_not_the_24_action_register():
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    report = reconstruct_authorization_register(payload, now=AS_OF)

    # The historical Phase-5 source extends beyond action ...0024, so it must
    # never be treated as the canonical 24-action APEX register by suffix/count.
    assert report.unique_action_ids > 24
    assert report.total_records >= report.unique_action_ids

    # These historical packets were created with bounded expiry windows; none
    # may silently become fresh authority on the fixed APEX review date.
    assert report.current_authority_count == 0

    # Reconstruction is read-only evidence classification. Duplicate or invalid
    # source data, if present, remains surfaced rather than normalized away.
    assert all(record.current_authority is False for record in report.records)
