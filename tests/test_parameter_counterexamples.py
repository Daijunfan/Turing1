from __future__ import annotations

import unittest

from src.clone_ascent.relations import clause_relation
from src.exact_parameters.joinwidth import exact_joinwidth
from src.exact_parameters.parameters import exact_parameter_bundle


class ParameterTests(unittest.TestCase):
    def test_joinwidth_uses_tuple_width_and_linear_restriction(self) -> None:
        relations = tuple(map(clause_relation, ((1, 2), (-2, 3), (-3, 1))))
        general = exact_joinwidth(relations, linear=False)
        linear = exact_joinwidth(relations, linear=True)
        self.assertEqual(general.status, "EXACT")
        self.assertLessEqual(general.value, linear.value)
        self.assertGreaterEqual(general.maximum_input_tuples, 1)

    def test_bundle_labels_exact_results(self) -> None:
        relations = tuple(map(clause_relation, ((1, 2), (-1, 2), (1, -2))))
        record = exact_parameter_bundle(relations)
        self.assertEqual(record["primal_treewidth"]["status"], "EXACT")
        self.assertEqual(record["general_joinwidth"]["status"], "EXACT")
        self.assertEqual(record["affine"]["backdoor_depth"]["status"], "EXACT")


if __name__ == "__main__":
    unittest.main()

