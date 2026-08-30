from __future__ import annotations

import copy
import unittest

from morphosat.fusion_certificate import (
    build_fusion_affine_unsat_certificate,
    verify_fusion_affine_unsat_certificate,
)
from morphosat.fusion_solver import MorphFusionSolver
from morphosat.generators import (
    generate_gate_hidden_2sat_chain,
    generate_gate_hidden_horn_cascade,
    generate_gate_obfuscated_tseitin,
)
from morphosat.solver import MorphSolver


class FusionTests(unittest.TestCase):
    def test_gate_tissue_affine_sat_and_unsat(self) -> None:
        for unsat in (False, True):
            inst = generate_gate_obfuscated_tseitin(
                8, unsat=unsat, seed=9100 + int(unsat), encoding="compact"
            )
            base = MorphSolver(8).solve(inst.cnf)
            self.assertEqual(base.status, "UNKNOWN")
            result = MorphFusionSolver(8, 8).solve(inst.cnf)
            self.assertEqual(result.status, inst.expected_status)
            self.assertTrue(result.verified)
            self.assertEqual(result.metrics["initial_common_classes"], [])
            self.assertTrue(result.metrics["emergent_common_classes"])

    def test_gate_tissue_bijunctive(self) -> None:
        for unsat in (False, True):
            inst = generate_gate_hidden_2sat_chain(24, unsat=unsat, seed=9200 + int(unsat))
            self.assertEqual(MorphSolver(8).solve(inst.cnf).status, "UNKNOWN")
            result = MorphFusionSolver(8, 8).solve(inst.cnf)
            self.assertEqual(result.status, inst.expected_status)
            self.assertTrue(result.verified)

    def test_gate_tissue_horn_family(self) -> None:
        for unsat in (False, True):
            inst = generate_gate_hidden_horn_cascade(16, unsat=unsat, seed=9300 + int(unsat))
            self.assertEqual(MorphSolver(8).solve(inst.cnf).status, "UNKNOWN")
            result = MorphFusionSolver(8, 8).solve(inst.cnf)
            self.assertEqual(result.status, inst.expected_status)
            self.assertTrue(result.verified)

    def test_standalone_fusion_certificate_and_tamper_detection(self) -> None:
        inst = generate_gate_obfuscated_tseitin(8, unsat=True, seed=8008, encoding="compact")
        cert = build_fusion_affine_unsat_certificate(inst.cnf, 8, 8)
        ok, detail = verify_fusion_affine_unsat_certificate(inst.cnf, cert)
        self.assertTrue(ok, detail)

        bad = copy.deepcopy(cert)
        bad["selected_equations"][0]["rhs"] ^= 1
        ok, _ = verify_fusion_affine_unsat_certificate(inst.cnf, bad)
        self.assertFalse(ok)

        bad_step = copy.deepcopy(cert)
        bad_step["fusion_steps"][0]["new_allowed"] = []
        ok, _ = verify_fusion_affine_unsat_certificate(inst.cnf, bad_step)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
