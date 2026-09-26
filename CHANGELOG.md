# Changelog

## 0.1.1 — unreleased

- Pass 7 check 2 now accepts an interface whose endpoints are covered by any package or any
  step, not only by a wave-1 step, so a correct rolling-wave plan passes. A plan with
  packages but no wave-1 steps still fails, on check 3 where it belongs (F1).
- The matrix input format pass 3 reads is documented here, in
  `skills/system-adoption-pipeline/references/MATRIX-INPUT.md`; the skill no longer defers it
  to another skill (F2).
- `scripts/test_interface_matrix.py` is vendored beside the pinned `interface_matrix.py`,
  pinned by sha256 and run in CI, so the pass-3 script can be verified from this skill
  alone (E2).
- Pass 4 takes pass 1's hot spots as input: each becomes a register row or is closed with a
  stated reason (F8).

## 0.1.0

- First release: the seven-pass system-adoption pipeline, seven templates, the pass-3
  interface matrix (vendored, sha256-pinned) and the pass-7 `check_plan.py` checker.
