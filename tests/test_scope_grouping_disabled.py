from __future__ import annotations

import unittest

from src.clone_ascent.models import clause_level_state, grouped_scope_state


class ScopeGroupingTests(unittest.TestCase):
    def test_clause_level_is_default_and_grouping_is_explicit(self) -> None:
        clauses = ((1, 2, 3), (-1, 2, 3), (1, -2, 3))
        clause_level = clause_level_state(clauses)
        legacy = grouped_scope_state(clauses)
        self.assertEqual(len(clause_level.active), len(clauses))
        self.assertEqual(len(legacy.active), 1)


if __name__ == "__main__":
    unittest.main()

