from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "morphosat_research"))

from morphosat.generators import generate_random_small_cnf
from morphosat.relations import discover_scope_blocks
from src.clone_ascent.models import initial_state
from src.clone_ascent.relations import Relation
from src.clone_ascent.search import SearchConfig, exact_clone_ascent


class LegacyRegressionTests(unittest.TestCase):
    def test_all_twenty_v02_exact_widths_replay(self) -> None:
        with (ROOT / "morphosat_research/results/exact_parameters.csv").open() as stream:
            expected = {
                row["instance_id"]: int(row["morph_width"])
                for row in csv.DictReader(stream)
            }
        for nvars in (4, 5):
            for seed in range(10):
                instance_id = f"random_exact.n{nvars}.s{seed}"
                cnf = generate_random_small_cnf(
                    nvars, nvars + 4, min(4, nvars), 10_000 + nvars * 100 + seed
                )
                relations = tuple(
                    Relation(block.scope, block.mask)
                    for block in discover_scope_blocks(cnf, 8)
                )
                result = exact_clone_ascent(
                    initial_state(relations),
                    SearchConfig(
                        model="LCA",
                        minimum_lca_parents=2,
                        max_births=nvars,
                        isomorphism_dedup=False,
                        legacy_empty_validity=True,
                    ),
                )
                width = min(item.cost.scope_width for item in result.frontier)
                self.assertEqual(width, expected[instance_id], instance_id)


if __name__ == "__main__":
    unittest.main()
