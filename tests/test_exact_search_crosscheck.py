from __future__ import annotations

import unittest

from src.clone_ascent.models import clause_level_state
from src.clone_ascent.search import SearchConfig, exact_clone_ascent, naive_clone_ascent


FORMULAS = (
    ((1, 2, 3), (-1, -2, -3)),
    ((1,), (-1, 2), (-2, 3), (-3,)),
    ((-1, -3), (-1, 3), (1, -3), (1, -2, 3), (2, 4), (3,)),
)


class ExactSearchCrosscheckTests(unittest.TestCase):
    def test_optimized_matches_naive(self) -> None:
        for formula in FORMULAS:
            for model in ("LCA", "BCA"):
                for recursive in (False, True):
                    for early in (False, True):
                        config = SearchConfig(
                            model=model,
                            max_births=3,
                            isomorphism_dedup=True,
                            recursive_births=recursive,
                            early_stop=early,
                        )
                        optimized = exact_clone_ascent(clause_level_state(formula), config)
                        naive = naive_clone_ascent(clause_level_state(formula), config)
                        self.assertEqual(optimized.minimum_births, naive.minimum_births)
                        self.assertEqual(
                            {item.cost.as_tuple() for item in optimized.frontier},
                            {item.cost.as_tuple() for item in naive.frontier},
                        )


if __name__ == "__main__":
    unittest.main()
