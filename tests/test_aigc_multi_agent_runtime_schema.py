from pathlib import Path
import pytest
import yaml
from scripts.validate_aigc_multi_agent_runtime import DEFAULT_CONFIG, DEFAULT_SCHEMA, validate_runtime

def test_invalid_schema_definition_is_rejected(tmp_path: Path):
    schema = yaml.safe_load(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    schema["type"] = "not-a-json-schema-type"
    altered = tmp_path / "schema.json"
    altered.write_text(__import__("json").dumps(schema), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON Schema definition"):
        validate_runtime(DEFAULT_CONFIG, altered)


def test_runtime_schema_and_graph_validate():
    result = validate_runtime()
    assert result["schema_validation"] == "PASS"
    assert result["graph_validation"] == "PASS"
    assert result["agent_count"] == 7
    assert result["production_activation_authorized"] is False

def test_runtime_defaults_keep_execution_and_external_effects_disabled():
    config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    defaults = config["runtime"]["defaults"]
    for key in ("agent_execution_enabled", "external_side_effects_enabled", "cloud_provisioning_enabled", "public_ingress_enabled", "business_cycle_enabled"):
        assert defaults[key] is False
    assert defaults["human_approval_required_for_release"] is True
    assert config["runtime"]["budgets"]["max_cost_cad"] == 0

def test_unknown_graph_node_is_rejected(tmp_path: Path):
    config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["orchestration_flow"]["edges"].append({"from": "planner", "to": "unregistered"})
    altered = tmp_path / "runtime.yaml"
    altered.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown node"):
        validate_runtime(altered, DEFAULT_SCHEMA)

def test_unsafe_execution_default_is_rejected_by_schema(tmp_path: Path):
    config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["runtime"]["defaults"]["agent_execution_enabled"] = True
    altered = tmp_path / "runtime.yaml"
    altered.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="schema validation failed"):
        validate_runtime(altered, DEFAULT_SCHEMA)

def test_tool_allowlist_cannot_be_enabled_without_followup_authorization(tmp_path: Path):
    config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["agents"]["coder"]["tools"] = ["git"]
    altered = tmp_path / "runtime.yaml"
    altered.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="tool allowlists"):
        validate_runtime(altered, DEFAULT_SCHEMA)


def test_orchestration_cycle_is_rejected(tmp_path: Path):
    config = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["orchestration_flow"]["edges"].append({"from": "orchestrator", "to": "planner"})
    altered = tmp_path / "runtime-cycle.yaml"
    altered.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="contains a cycle"):
        validate_runtime(altered, DEFAULT_SCHEMA)
