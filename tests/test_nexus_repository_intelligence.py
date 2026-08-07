import json
from pathlib import Path

from scripts.nexus_repository_intelligence import analyze


def test_repository_intelligence_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "a.py").write_text("import src.b\n\ndef alpha():\n    if True:\n        return 1\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("def beta():\n    return 2\n", encoding="utf-8")
    (tmp_path / "tests" / "test_a.py").write_text("import src.a\n\ndef test_alpha():\n    assert True\n", encoding="utf-8")

    first = analyze(tmp_path)
    second = analyze(tmp_path)

    assert first == second
    assert first["summary"]["source_files"] == 2
    assert first["summary"]["test_files"] == 1
    assert first["python"]["python_modules"] == 3
    assert first["python"]["internal_import_edges"] >= 2
    assert first["test_capability_ownership"]["source_modules_with_direct_test_import"] >= 1
    assert first["report_sha256"]


def test_repository_intelligence_detects_exact_duplicates(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("same\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("same\n", encoding="utf-8")

    report = analyze(tmp_path)

    assert report["duplication"]["exact_duplicate_groups"] == 1
    assert report["duplication"]["exact_duplicate_files"] == 2


def test_repository_intelligence_ignores_virtual_environment(tmp_path: Path) -> None:
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.py").write_text("raise RuntimeError\n", encoding="utf-8")
    (tmp_path / "kept.py").write_text("VALUE = 1\n", encoding="utf-8")

    report = analyze(tmp_path)

    assert report["summary"]["total_files"] == 1


def test_repository_intelligence_detects_import_cycle(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("import src.b\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("import src.a\n", encoding="utf-8")

    report = analyze(tmp_path)

    assert report["python"]["import_cycle_count"] == 1
    assert report["python"]["import_cycles"] == [["src.a", "src.b"]]


def test_repository_intelligence_flags_schema_overlap_candidates(tmp_path: Path) -> None:
    (tmp_path / "schemas").mkdir()
    shared = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["id", "status"],
        "properties": {
            "id": {"type": "string"},
            "status": {"enum": ["active", "blocked"]},
            "reason": {"type": "string"},
        },
    }
    left = dict(shared)
    right = dict(shared)
    right["properties"] = dict(shared["properties"], note={"type": "string"})
    (tmp_path / "schemas" / "left.schema.json").write_text(json.dumps(left), encoding="utf-8")
    (tmp_path / "schemas" / "right.schema.json").write_text(json.dumps(right), encoding="utf-8")

    report = analyze(tmp_path)

    assert report["schema_semantic_overlap"]["schema_count"] == 2
    assert report["schema_semantic_overlap"]["overlap_candidate_count"] == 1
    assert report["schema_semantic_overlap"]["top_overlap_candidates"][0]["jaccard"] > 0.5


def test_repository_intelligence_maps_test_ownership_by_import(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "owned.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "src" / "unowned.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "tests" / "test_owned.py").write_text("import src.owned\n", encoding="utf-8")

    report = analyze(tmp_path)
    ownership = report["test_capability_ownership"]

    assert ownership["source_modules_with_direct_test_import"] == 1
    assert ownership["source_modules_without_direct_test_import_count"] == 1
    assert "src.unowned" in ownership["source_modules_without_direct_test_import"]
