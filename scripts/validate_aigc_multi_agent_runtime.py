from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "aigc_multi_agent_runtime.yaml"
DEFAULT_SCHEMA = ROOT / "schemas" / "aigc_multi_agent_runtime.schema.json"
def validate_runtime(config_path: Path = DEFAULT_CONFIG, schema_path: Path = DEFAULT_SCHEMA) -> dict:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"Invalid JSON Schema definition: {exc.message}") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(config), key=lambda e: (list(map(str, e.absolute_path)), e.message))
    if errors:
        details = "; ".join(f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors)
        raise ValueError(f"AIGC runtime schema validation failed: {details}")
    agents = config["agents"]
    if any(agent["id"] != key for key, agent in agents.items()): raise ValueError("agent mapping keys must match declared agent IDs")
    if any(agent["tools"] for agent in agents.values()): raise ValueError("tool allowlists must remain empty until explicit runtime authorization")
    flow = config["orchestration_flow"]; nodes = set(flow["nodes"])
    if nodes != set(agents): raise ValueError("orchestration nodes must exactly match declared agents")
    for edge in flow["edges"]:
        if edge.get("from") not in nodes or edge.get("to") not in nodes: raise ValueError(f"orchestration edge references unknown node: {edge}")
    adjacency = {node: [] for node in nodes}
    for edge in flow["edges"]:
        adjacency[edge["from"]].append(edge["to"])
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError(f"orchestration graph contains a cycle at node: {node}")
        if node in visited:
            return
        visiting.add(node)
        for child in adjacency[node]:
            visit(child)
        visiting.remove(node)
        visited.add(node)
    for node in sorted(nodes):
        visit(node)
    if not set(flow["join_policy"]["orchestrator_requires"]).issubset(nodes): raise ValueError("join policy requires an undeclared agent")
    return {"schema_validation":"PASS","graph_validation":"PASS","agent_count":len(agents),"edge_count":len(flow["edges"]),"agent_execution_enabled":config["runtime"]["defaults"]["agent_execution_enabled"],"external_side_effects_enabled":config["runtime"]["defaults"]["external_side_effects_enabled"],"cloud_provisioning_enabled":config["runtime"]["defaults"]["cloud_provisioning_enabled"],"public_ingress_enabled":config["runtime"]["defaults"]["public_ingress_enabled"],"production_activation_authorized":False}
def main() -> int:
    parser=argparse.ArgumentParser(description="Validate the declarative AIGC multi-agent runtime contract.")
    parser.add_argument("--config",type=Path,default=DEFAULT_CONFIG); parser.add_argument("--schema",type=Path,default=DEFAULT_SCHEMA); args=parser.parse_args()
    try: result=validate_runtime(args.config,args.schema)
    except (OSError,ValueError,json.JSONDecodeError,yaml.YAMLError) as exc: print(str(exc),file=sys.stderr); return 1
    print(json.dumps(result,sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
