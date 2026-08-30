#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from morphosat.certificate import read_certificate, verify_affine_unsat_certificate
from morphosat.cnf import CNF


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cnf")
    p.add_argument("certificate")
    args = p.parse_args()
    cnf = CNF.from_dimacs(args.cnf)
    ok, detail = verify_affine_unsat_certificate(cnf, read_certificate(args.certificate))
    print(json.dumps({"verified": ok, "detail": detail}, indent=2, sort_keys=True))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
