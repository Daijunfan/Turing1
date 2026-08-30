from morphosat.generators import generate_obfuscated_tseitin
from morphosat.solver import MorphSolver
from morphosat.z3ffi import Z3FFI
import json, time

solver=MorphSolver(max_arity=8)
z3=Z3FFI()
for n in [16,32,64,128,256,512,1024]:
    inst=generate_obfuscated_tseitin(n, degree=3, private_per_vertex=2, unsat=True, seed=100+n)
    t=time.perf_counter(); r=solver.solve(inst.cnf); mt=time.perf_counter()-t
    zr=z3.solve(inst.cnf, timeout_ms=3000, seed=1)
    print(json.dumps({
        'vertices':n,'vars':inst.cnf.nvars,'clauses':len(inst.cnf.clauses),
        'morph_status':r.status,'morph_verified':r.verified,'morph_time':mt,
        'births':r.metrics.get('concept_births'),'depth':r.metrics.get('concept_depth'),
        'cert_eqs':r.certificate.get('certificate_equations'),
        'z3_status':zr.status,'z3_time':zr.elapsed_seconds,'z3_stats':zr.stats_text,
    }))
