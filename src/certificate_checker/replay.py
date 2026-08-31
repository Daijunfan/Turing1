from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from src.clone_ascent.models import AscentState
from src.clone_ascent.polymorphisms import (
    common_signature,
    gained_operations,
    gained_witnesses,
    signature_hex,
    signature_names,
)
from src.clone_ascent.relations import Relation, clause_relation


def build_certificate(state: AscentState, source_clauses: Iterable[tuple[int, ...]] | None = None) -> dict[str, object]:
    initial = [node.to_dict() for node in state.history if not node.parents]
    payload: dict[str, object] = {
        "format": "CLONE-ASCENT-CERTIFICATE-v1",
        "initial_relations": initial,
        "steps": [step.to_dict() for step in state.steps],
        "endpoint_signature": signature_hex(state.signature),
        "endpoint_witnesses": list(signature_names(state.signature)),
        "cost": state.cost.to_dict(),
    }
    if source_clauses is not None:
        payload["source_clauses"] = [list(clause) for clause in source_clauses]
    return payload


def write_certificate(path: str | Path, certificate: dict[str, object]) -> None:
    Path(path).write_text(json.dumps(certificate, indent=2, sort_keys=True), encoding="utf-8")


def _relation(data: dict[str, object]) -> Relation:
    return Relation(tuple(int(value) for value in data["scope"]), int(data["mask"]))  # type: ignore[index]


def _independent_contract(parents: list[Relation], eliminate: set[int]) -> Relation:
    union = tuple(sorted({variable for parent in parents for variable in parent.scope}))
    union_position = {variable: index for index, variable in enumerate(union)}
    keep = tuple(variable for variable in union if variable not in eliminate)
    output_mask = 0
    for union_bits in range(1 << len(union)):
        valid = True
        for parent in parents:
            local = 0
            for index, variable in enumerate(parent.scope):
                local |= ((union_bits >> union_position[variable]) & 1) << index
            if not parent.holds_bits(local):
                valid = False
                break
        if not valid:
            continue
        projected = 0
        for index, variable in enumerate(keep):
            projected |= ((union_bits >> union_position[variable]) & 1) << index
        output_mask |= 1 << projected
    return Relation(keep, output_mask)


def replay_certificate(
    certificate: dict[str, object],
    expected_clauses: Iterable[tuple[int, ...]] | None = None,
) -> tuple[bool, dict[str, object]]:
    if certificate.get("format") != "CLONE-ASCENT-CERTIFICATE-v1":
        return False, {"error": "unsupported certificate format"}
    initial_data = certificate.get("initial_relations")
    steps = certificate.get("steps")
    if not isinstance(initial_data, list) or not isinstance(steps, list):
        return False, {"error": "missing initial relations or steps"}
    active: dict[int, Relation] = {}
    for node in initial_data:
        if not isinstance(node, dict) or not isinstance(node.get("relation"), dict):
            return False, {"error": "malformed initial relation"}
        relation_id = int(node["relation_id"])
        active[relation_id] = _relation(node["relation"])
    if expected_clauses is not None:
        expected = sorted(clause_relation(tuple(clause)) for clause in expected_clauses)
        if sorted(active.values()) != expected:
            return False, {"error": "initial relations do not match clause-level CNF"}
    monotone = True
    signatures = [common_signature(active.values())]
    snapshots = [{
        "step": 0,
        "relation_count": len(active),
        "max_scope": max((relation.arity for relation in active.values()), default=0),
        "table_size": sum(relation.tuple_count for relation in active.values()),
        "signature": signature_hex(signatures[-1]),
        "witnesses": list(signature_names(signatures[-1])),
        "generation_depth": 0,
        "new_operations": [],
        "new_witnesses": [],
    }]
    depths = {relation_id: 0 for relation_id in active}
    for index, step_data in enumerate(steps, 1):
        if not isinstance(step_data, dict):
            return False, {"error": f"malformed step {index}"}
        parent_ids = tuple(int(item) for item in step_data["parent_ids"])  # type: ignore[index]
        if not parent_ids or any(parent not in active for parent in parent_ids):
            return False, {"error": f"step {index} has inactive parent"}
        eliminate = {int(item) for item in step_data["eliminated"]}  # type: ignore[index]
        outside = set().union(*(
            set(relation.scope) for relation_id, relation in active.items() if relation_id not in parent_ids
        )) if len(active) > len(parent_ids) else set()
        if eliminate & outside:
            return False, {"error": f"step {index} projects an externally live variable"}
        parents = [active[parent] for parent in parent_ids]
        child = _independent_contract(parents, eliminate)
        claimed = _relation(step_data["child"])  # type: ignore[arg-type,index]
        if child != claimed:
            return False, {"error": f"step {index} child truth table mismatch"}
        for parent in parent_ids:
            del active[parent]
        new_id = int(step_data["new_relation_id"])
        if new_id in active:
            return False, {"error": f"step {index} reuses active relation id"}
        active[new_id] = child
        depth = max(depths[parent] for parent in parent_ids) + 1
        depths[new_id] = depth
        after = common_signature(active.values())
        if signatures[-1] & ~after:
            monotone = False
            return False, {"error": f"step {index} violates signature monotonicity"}
        signatures.append(after)
        snapshots.append({
            "step": index,
            "relation_count": len(active),
            "max_scope": max((relation.arity for relation in active.values()), default=0),
            "table_size": sum(relation.tuple_count for relation in active.values()),
            "signature": signature_hex(after),
            "witnesses": list(signature_names(after)),
            "generation_depth": max(depths[relation_id] for relation_id in active),
            "new_operations": [list(operation) for operation in gained_operations(signatures[-2], after)],
            "new_witnesses": list(gained_witnesses(signatures[-2], after)),
        })
    endpoint = common_signature(active.values())
    if certificate.get("endpoint_signature") != signature_hex(endpoint):
        return False, {"error": "endpoint signature mismatch"}
    return True, {
        "verified_steps": len(steps),
        "monotone": monotone,
        "endpoint_signature": signature_hex(endpoint),
        "endpoint_witnesses": list(signature_names(endpoint)),
        "snapshots": snapshots,
    }
