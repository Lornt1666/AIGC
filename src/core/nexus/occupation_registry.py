from __future__ import annotations

import json
from pathlib import Path

from src.domain.nexus.occupation import OccupationPack


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PACK_DIRECTORY = PROJECT_ROOT / "config" / "occupation_packs"


def load_occupation_packs(directory: Path = DEFAULT_PACK_DIRECTORY) -> tuple[OccupationPack, ...]:
    """Load the closed local occupation-pack catalogue without network access."""

    packs: list[OccupationPack] = []
    for path in sorted(directory.glob("*.json")):
        packs.append(OccupationPack.model_validate(json.loads(path.read_text(encoding="utf-8"))))
    ids = [item.pack_id for item in packs]
    if len(ids) != len(set(ids)):
        raise ValueError("occupation pack IDs must be globally unique")
    return tuple(packs)


def occupation_pack_snapshot(directory: Path = DEFAULT_PACK_DIRECTORY) -> tuple[dict[str, object], ...]:
    """Return a safe, explicit projection; packs never grant execution authority."""

    return tuple(pack.model_dump(mode="json") for pack in load_occupation_packs(directory))
