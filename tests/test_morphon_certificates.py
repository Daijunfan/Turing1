from __future__ import annotations

import copy
import unittest

from src.certificate_checker.replay import build_certificate, replay_certificate
from src.morphon_synthesis.synthesis import check_morphon


AFFINE_MORPHON = ((-1, -3), (-1, 3), (1, -3), (1, -2, 3), (2, 4), (3,))


class MorphonCertificateTests(unittest.TestCase):
    def test_certificate_replays_and_tampering_fails(self) -> None:
        check = check_morphon(AFFINE_MORPHON, "affine")
        self.assertTrue(check.valid)
        self.assertIsNotNone(check.witness_state)
        certificate = build_certificate(check.witness_state, AFFINE_MORPHON)  # type: ignore[arg-type]
        ok, detail = replay_certificate(certificate, AFFINE_MORPHON)
        self.assertTrue(ok, detail)
        bad = copy.deepcopy(certificate)
        bad["steps"][0]["child"]["mask"] ^= 1
        ok, _ = replay_certificate(bad, AFFINE_MORPHON)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()

