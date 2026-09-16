# Gate C attestation

Independent run per `docs/evaluation/independent-exercise.md`.

| Field | Value |
|---|---|
| Exerciser name | Chanukya Lakamsani |
| Affiliation | University of Cumberlands / Information Technology |
| Date | 2026-09-15 |
| Git commit SHA | 27d8b6aed027a57963de1c122b59b99743c477e4 |
| `tamper_detection_rate` | 19/19 |
| `independently_verified_arc` | 20/20 |
| `false_tamper_rate` | 0/3 |
| Signature | /s/ Chanukya Lakamsani, 2026-09-15 |

**Note:** Clean clone at tag `jbhi-eval-20260828`. Tamper/benchmark pytest (`tests/unit/test_verifier_tamper.py`, `tests/evaluation/test_benchmark.py`): 15 passed. Evaluation: `CAP_LLM_PROVIDER=stub curie-audit-plane evaluate --output-dir /tmp/cap-gate-c --encounters 1 --repetitions 1`. Metrics from `evaluation-report.json` (`experiment.git_commit` matches SHA above; `git_dirty: false`). Python 3.13.7, deterministic stub provider. Pytest run with `--no-cov` because project-wide coverage threshold fails when only Gate C tests are selected.

**Status: Gate C satisfied per independent-exercise.md.**
