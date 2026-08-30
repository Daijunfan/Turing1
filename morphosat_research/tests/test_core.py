from __future__ import annotations

import unittest

from morphosat.affine import affine_relation_equations, verify_affine_relation
from morphosat.bruteforce import solve_bruteforce
from morphosat.cnf import CNF
from morphosat.generators import (
    encode_relation,
    generate_hidden_2sat_chain,
    generate_hidden_horn_cascade,
    generate_obfuscated_tseitin,
    generate_random_small_cnf,
)
from morphosat.solver import MorphSolver
from morphosat.z3ffi import Z3FFI


class CoreTests(unittest.TestCase):
    def test_affine_relation_recovery(self) -> None:
        # x xor y xor z = 1
        allowed = tuple(t for t in range(8) if t.bit_count() % 2 == 1)
        ok, eqs = affine_relation_equations(allowed, 3)
        self.assertTrue(ok)
        self.assertTrue(verify_affine_relation(allowed, 3, eqs))
        self.assertEqual(len(eqs), 1)

    def test_affine_unsat_certificate(self) -> None:
        instance = generate_obfuscated_tseitin(12, private_per_vertex=1, unsat=True, seed=3)
        result = MorphSolver().solve(instance.cnf)
        self.assertEqual(result.status, "UNSAT")
        self.assertTrue(result.verified)
        self.assertTrue(result.certificate["global_xor_certificate_verified"])

    def test_affine_sat_model(self) -> None:
        instance = generate_obfuscated_tseitin(12, private_per_vertex=1, unsat=False, seed=4)
        result = MorphSolver().solve(instance.cnf)
        self.assertEqual(result.status, "SAT")
        self.assertTrue(result.verified)
        self.assertIsNotNone(result.assignment)
        self.assertTrue(instance.cnf.is_satisfied(result.assignment))

    def test_hidden_2sat(self) -> None:
        for unsat in (False, True):
            instance = generate_hidden_2sat_chain(40, unsat=unsat, seed=11)
            result = MorphSolver().solve(instance.cnf)
            self.assertEqual(result.status, instance.expected_status)
            self.assertTrue(result.verified)

    def test_hidden_horn(self) -> None:
        for unsat in (False, True):
            instance = generate_hidden_horn_cascade(40, unsat=unsat, seed=12)
            result = MorphSolver().solve(instance.cnf)
            self.assertEqual(result.status, instance.expected_status)
            self.assertTrue(result.verified)

    def test_z3_ffi(self) -> None:
        cnf = CNF(1, [(1,), (-1,)])
        result = Z3FFI().solve(cnf, timeout_ms=1000)
        self.assertEqual(result.status, "UNSAT")

    def test_random_fuzz_against_bruteforce(self) -> None:
        solver = MorphSolver(max_arity=6)
        checked = 0
        for seed in range(300):
            cnf = generate_random_small_cnf(
                nvars=6,
                nclauses=8 + (seed % 7),
                max_width=4,
                seed=seed,
            )
            expected, _ = solve_bruteforce(cnf)
            result = solver.solve(cnf)
            if result.status != "UNKNOWN":
                checked += 1
                self.assertEqual(result.status, expected, msg=f"seed={seed}")
                self.assertTrue(result.verified, msg=f"seed={seed}")
        self.assertGreater(checked, 25)


if __name__ == "__main__":
    unittest.main()
