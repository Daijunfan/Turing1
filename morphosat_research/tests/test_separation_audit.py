from __future__ import annotations

import unittest

from morphosat.audit_fusion import discover_clause_relations, run_ablation_fusion
from morphosat.audit_generators import generate_heterogeneous_tseitin, verify_xor_templates
from morphosat.exact_width import brute_force_morph_width, exact_morph_width
from morphosat.generators import generate_random_small_cnf
from morphosat.parameters import compute_parameter_record
from morphosat.relations import discover_scope_blocks


class SeparationAuditTests(unittest.TestCase):
    def test_heterogeneous_xor_templates_are_exact(self) -> None:
        self.assertTrue(all(verify_xor_templates().values()))

    def test_exact_width_matches_independent_enumeration(self) -> None:
        cnf = generate_random_small_cnf(4, 8, 4, 10402)
        blocks = discover_scope_blocks(cnf, 8)
        exact = exact_morph_width(blocks)
        self.assertEqual(exact.min_width, brute_force_morph_width(blocks, 3))
        self.assertTrue(exact.exhaustive)

    def test_parameter_kinds_are_explicit(self) -> None:
        cnf = generate_random_small_cnf(4, 7, 3, 2201)
        record = compute_parameter_record(cnf, discover_scope_blocks(cnf, 8))
        self.assertIn(record["primal_treewidth_kind"], {"exact", "bounds"})
        self.assertEqual(record["affine_strong_backdoor_kind"], "exact")

    def test_scope_recovery_is_a_real_ablation(self) -> None:
        instance = generate_heterogeneous_tseitin(4, True, 8, split_relations=False)
        recovered = run_ablation_fusion(discover_scope_blocks(instance.cnf, 8), 8)
        clausewise = run_ablation_fusion(discover_clause_relations(instance.cnf), 8)
        self.assertTrue(recovered.success)
        self.assertTrue(clausewise.success)
        self.assertGreaterEqual(clausewise.total_relation_table_size, recovered.total_relation_table_size)


if __name__ == "__main__":
    unittest.main()
