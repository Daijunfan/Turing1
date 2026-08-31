from __future__ import annotations

import random
import unittest

from src.clone_ascent.models import bca_successors, clause_level_state, lca_successors
from src.clone_ascent.polymorphisms import OPERATIONS


class CloneMonotonicityTests(unittest.TestCase):
    def test_all_276_operations_are_present(self) -> None:
        self.assertEqual(len(OPERATIONS), 276)
        self.assertEqual(sum(arity == 1 for arity, _ in OPERATIONS), 4)
        self.assertEqual(sum(arity == 2 for arity, _ in OPERATIONS), 16)
        self.assertEqual(sum(arity == 3 for arity, _ in OPERATIONS), 256)

    def test_every_generated_step_is_signature_monotone(self) -> None:
        rng = random.Random(3003)
        literals = (1, -1, 2, -2, 3, -3)
        for _ in range(40):
            clauses = []
            for _ in range(rng.randint(3, 6)):
                variables = rng.sample((1, 2, 3), rng.randint(1, 3))
                clauses.append(tuple(variable if rng.getrandbits(1) else -variable for variable in variables))
            state = clause_level_state(clauses)
            for successor in lca_successors(state) + bca_successors(state):
                self.assertEqual(state.signature & ~successor.signature, 0)


if __name__ == "__main__":
    unittest.main()

