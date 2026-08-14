from pathlib import Path

from scripts.nexus_repository_intelligence import analyze


def test_repository_intelligence_resolves_most_specific_module(tmp_path: Path) -> None:
    (tmp_path / "src" / "core" / "nexus").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "core" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "core" / "nexus" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "core" / "nexus" / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_engine.py").write_text("import src.core.nexus.engine\n", encoding="utf-8")

    report = analyze(tmp_path)
    ownership = report["test_capability_ownership"]

    assert "src.core.nexus.engine" not in ownership["source_modules_without_direct_test_import"]
    assert any(
        item["source"] == "src.core.nexus.engine" and item["test_modules"] == 1
        for item in ownership["heavily_tested_source_modules"]
    )
