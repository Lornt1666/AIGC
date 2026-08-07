from pathlib import Path

from scripts.nexus_repository_intelligence import analyze


def test_repository_intelligence_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "a.py").write_text("import src.b\n\ndef alpha():\n    if True:\n        return 1\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("def beta():\n    return 2\n", encoding="utf-8")
    (tmp_path / "tests" / "test_a.py").write_text("def test_alpha():\n    assert True\n", encoding="utf-8")

    first = analyze(tmp_path)
    second = analyze(tmp_path)

    assert first == second
    assert first["summary"]["source_files"] == 2
    assert first["summary"]["test_files"] == 1
    assert first["python"]["python_modules"] == 3
    assert first["python"]["internal_import_edges"] >= 1
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
