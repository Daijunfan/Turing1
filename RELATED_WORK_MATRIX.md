# Related-work matrix

| Object | Established result used here | Relation to v0.3 | Status in this repository |
|---|---|---|---|
| pp-definability and polymorphisms | Polymorphisms preserve natural joins and existential projections | Directly proves clone-signature monotonicity | `PROVED`; explicitly not claimed new |
| Schaefer Boolean CSP classes | Constants, AND, OR, majority and minority witness standard tractable languages | Endpoint filters for clone ascent | `PROVED` definitions; exact low-arity checks |
| Bucket/variable elimination | Eliminating a variable joins all incident constraints and projects it | LCA, and v0.1 MORPH as an early-stop special case | `PROVED`, 20/20 v0.2 replay |
| Ganian--Ordyniak--Szeider joinwidth | Binary join tree, separator projection, pruning, width `log_(#tup) |C(j)|` | Nearest tuple-sensitive parameter; not scope width | Exact Definition-3 implementation for small instances |
| Linear joinwidth | Join decomposition with a leaf child at every internal node | Nearest published linear join plan | Exact dynamic program for small instances |
| Strong Schaefer backdoors | Assign a variable set so every branch enters a target class | Compared with CAF | Exact small-instance enumeration |
| Backdoor depth / recursive depth | Decision depth, with component decomposition for recursive depth | Dynamic nearest neighbours | Exact small-instance recursion |
| Backdoor-treewidth | Treewidth of the torso of a strong backdoor | Hybrid structural/language parameter | Exact small-instance enumeration |
| Tseitin Resolution lower bounds | Expansion/treewidth yields large width/size for ordinary hard cores | Potential outer core for lifting | Not transferable to current locally UNSAT gadgets |
| Proof-complexity lifting | Requires a gadget meeting explicit simulation/stifling hypotheses | Candidate future route | Current catalog fails applicability |

Primary joinwidth source: Robert Ganian, Sebastian Ordyniak, Stefan Szeider,
*A Join-Based Hybrid Parameter for Constraint Satisfaction*, CP 2019,
https://arxiv.org/abs/1907.12335.

