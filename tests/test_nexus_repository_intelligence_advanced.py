from pathlib import Path
import subprocess

from scripts.nexus_repository_intelligence_advanced import analyze_advanced


def _git(root: Path, *args: str) -> None:
    subprocess.check_call(["git", "-C", str(root), *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_advanced_analytics_trace_schema_callers_and_transitive_tests(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "alpha.schema.json").write_text(
        '{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","properties":{"id":{"type":"string"}}}',
        encoding="utf-8",
    )
    (tmp_path / "src" / "service.py").write_text(
        'SCHEMA = "schemas/alpha.schema.json"\n\ndef run():\n    return 1\n', encoding="utf-8"
    )
    (tmp_path / "src" / "api.py").write_text("from src.service import run\n", encoding="utf-8")
    (tmp_path / "tests" / "test_api.py").write_text("import src.api\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest>=8,<9\n", encoding="utf-8")

    report = analyze_advanced(tmp_path)

    assert report["schema_caller_analysis"]["schemas_with_callers"] == 1
    assert report["indirect_test_ownership"]["source_modules_with_transitive_test_reachability"] >= 2
    assert report["dependency_usage"]["direct_dependency_count"] == 1


def test_advanced_analytics_marks_responsibility_mapping_as_heuristic(tmp_path: Path) -> None:
    (tmp_path / "src" / "core" / "nexus").mkdir(parents=True)
    (tmp_path / "src" / "core" / "nexus" / "state_reducer.py").write_text(
        "def reduce_state():\n    return None\n", encoding="utf-8"
    )
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")

    report = analyze_advanced(tmp_path)
    bucket = report["canonical_responsibilities"]["state_machine"]

    assert bucket["classification"] == "HEURISTIC_CANDIDATE_MAP_NOT_AUTHORITY"
    assert "src.core.nexus.state_reducer" in bucket["canonical_targets_present"]
    assert report["partial_ecs_inputs"]["subsystems"][0]["ecs"] is None


def test_branch_analytics_are_observational(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "tests@example.invalid")
    _git(tmp_path, "config", "user.name", "AIGC Tests")
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "baseline")
    _git(tmp_path, "branch", "-M", "main")
    _git(tmp_path, "remote", "add", "origin", str(tmp_path))
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(tmp_path, "branch", "feature-test")
    _git(tmp_path, "update-ref", "refs/remotes/origin/feature-test", "HEAD")

    report = analyze_advanced(tmp_path)

    assert report["branch_analytics"]["remote_branch_count"] >= 2
