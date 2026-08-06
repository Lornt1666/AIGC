from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Mapping


class GraphValidationError(ValueError):
    pass


def validate_graph(graph: Mapping[str, Any]) -> None:
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not nodes:
        raise GraphValidationError("graph requires nodes")
    if not isinstance(edges, list):
        raise GraphValidationError("graph requires an edge list")
    node_ids: set[str] = set()
    external_nodes: set[str] = set()
    loop_nodes: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("node_id"), str):
            raise GraphValidationError("every node requires node_id")
        node_id = node["node_id"]
        if node_id in node_ids:
            raise GraphValidationError("duplicate node_id")
        node_ids.add(node_id)
        if node.get("external_effect") is True:
            external_nodes.add(node_id)
            if not node.get("authorization_digest"):
                raise GraphValidationError("external node lacks authorization")
            if not node.get("idempotency_key_digest"):
                raise GraphValidationError("external node lacks idempotency")
        if node.get("node_type") == "BOUNDED_LOOP":
            maximum = node.get("maximum_iterations")
            if not isinstance(maximum, int) or not 1 <= maximum <= 100:
                raise GraphValidationError("bounded loop requires maximum_iterations")
            loop_nodes.add(node_id)
        if not node.get("output_schema_digest"):
            raise GraphValidationError("every node requires output schema")
    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in node_ids}
    for edge in edges:
        if not isinstance(edge, dict):
            raise GraphValidationError("edge must be an object")
        source, target = edge.get("source"), edge.get("target")
        if source not in node_ids or target not in node_ids:
            raise GraphValidationError("edge references unknown node")
        if source == target and source not in loop_nodes:
            raise GraphValidationError("self-cycle requires bounded loop")
        if source != target:
            adjacency[source].append(target)
            indegree[target] += 1
    queue = deque(node for node, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for target in adjacency[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(node_ids):
        raise GraphValidationError("unbounded cycle detected")
