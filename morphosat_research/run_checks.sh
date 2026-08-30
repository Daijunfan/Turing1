#!/usr/bin/env bash
set -euo pipefail
python3 -m compileall -q morphosat tests experiments solve.py verify_model.py verify_certificate.py verify_fusion_certificate.py
python3 -m unittest discover -s tests -v
python3 verify_certificate.py results/flagship_direct_8192.cnf results/flagship_direct_8192.cert.json
python3 verify_fusion_certificate.py results/flagship_gate_fusion_192.cnf results/flagship_gate_fusion_192.cert.json
python3 verify_model.py results/flagship_direct_8192_sat.cnf results/flagship_direct_8192_sat.model.json
python3 verify_model.py results/flagship_gate_fusion_192_sat.cnf results/flagship_gate_fusion_192_sat.model.json
