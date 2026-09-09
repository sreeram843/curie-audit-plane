# Independent integrity exercise (Gate C)

PRD Gate C requires the verifier and tamper benchmark to be exercised by
someone who **did not implement them**. This file is the protocol. It is not
itself an attestation.

The in-repository verifier lives in `src/curie_audit_plane/integrity/verifier.py`.
The labeled mutation suite is driven by `src/curie_audit_plane/evaluation/benchmark.py`
and reported as `tamper_detection_rate`.

## Who may sign

A second person (not the author of the verifier or mutation labels) on a
clean clone of a tagged commit. Coding agents that implemented the verifier
cannot satisfy Gate C.

## Commands

From a clean clone of tag `jbhi-eval-20260828` (or the commit under test):

```bash
uv sync
uv run pytest tests/unit/test_verifier_tamper.py tests/evaluation/test_benchmark.py -q
CAP_LLM_PROVIDER=stub uv run curie-audit-plane evaluate --output-dir /tmp/cap-gate-c --encounters 1 --repetitions 1
```

## Pass criteria

- Tamper tests pass.
- `tamper_detection_rate` is `19/19`.
- `independently_verified_arc` is `20/20` after reload.
- `false_tamper_rate` is `0` over the clean cases in that report.

Record the git commit, date, and a short note in
`papers/jbhi/GATE_C_ATTESTATION.md`. Leave that file unsigned until a second
person actually runs the commands.
