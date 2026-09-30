# Changelog

## Unreleased

(none)

## 0.4.0 — 2026-09-30

- Re-vendored `interface_matrix.py` and `test_interface_matrix.py` from interface-matrix
  [v0.4.0](https://github.com/macblackstuff/interface-matrix/releases/tag/v0.4.0), pinned by
  sha256 with the tag recorded in `scripts/interface_matrix.UPSTREAM`. The vendored matrix
  gains the certification gate: `--certify LEDGER` checks the input against an
  identity-keyed review ledger, exits 3 naming every `drifted:`/`unreviewed:` blocker,
  writes a certification record beside the ledger, and carries `open` gap dispositions as
  advisories. Its self-check is now 115 tests.
- Pass 3's done-check requires the matrix to certify: `--certify` exits 0, with the review
  recorded in the ledger.
- Pass 3's review is separation of duties, reworded in SKILL.md and the README: the
  reviewer of record the ledger names is distinct from whatever drafted the input —
  independent human review by default, a model reviewer only when the user explicitly
  pinned one (arXiv 2312.04134 is the independence rationale).
- `references/MATRIX-INPUT.md` documents the certification duties beside the input format:
  the seven-column ledger, exit 0 as pass-3 completion, `open-parked` gap parking, drift,
  and the four-file deliverable — report, certification record, input, ledger.
- CI's and the runbook's standard-library allow-list gain `hashlib` and `json`, the
  vendored matrix's new imports.

## 0.3.0 — 2026-09-29

- Re-vendored `interface_matrix.py` and `test_interface_matrix.py` from interface-matrix
  [v0.3.0](https://github.com/macblackstuff/interface-matrix/releases/tag/v0.3.0), pinned by
  sha256 with the tag recorded in `scripts/interface_matrix.UPSTREAM`. The vendored matrix
  now writes UTF-8 on every platform (Windows legacy codepages no longer crash it) and its
  self-check gained the non-UTF8-console regression test: 84 tests.
- README rewritten to the public-readme standard: a worked pass-3 example with its real
  output, per-harness install table, and runnable commands for both scripts. The status
  badges are removed.
- CI installs and self-tests the skill for every agent the `skills` CLI supports, with the
  agent list read from the CLI at run time.
- Copyright holder in `LICENSE` and the README is now `macblackstuff`.
- Code of conduct (Contributor Covenant 2.1); reports go to `conduct@macblackstuff.com`.

## 0.2.1 — 2026-09-26

- Moved to [github.com/macblackstuff/system-adoption-pipeline](https://github.com/macblackstuff/system-adoption-pipeline);
  every link and install command now uses the new owner. The old `macblackstuff-labs` URLs redirect.
- `scripts/interface_matrix.UPSTREAM` records the new upstream location. The vendored files and
  their pins are unchanged.
- Contributing guide, issue forms and pull request template; README badges; release
  headings dated.

## 0.2.0 — 2026-09-26

- Re-vendored `interface_matrix.py` and `test_interface_matrix.py` from interface-matrix
  v0.2.0, pinned by sha256 with the tag recorded in `interface_matrix.UPSTREAM`. The matrix
  now decides `external` by the same token rule as `check_plan.py` (F4), and warns on stderr
  when a misspelled Components, Interfaces or Rules header makes it skip a table.
  `references/MATRIX-INPUT.md` documents both, and the Rules table's optional `Status`.
  CI's and the runbook's standard-library allow-list gain `difflib`.
- CI's pin job fails when two pins share a basename, so they cannot check the same file.
- Pass 7 check 2: an endpoint id the inventory does not know fails as a pass-3 defect (E5);
  an interface between two externals is exempt and not counted as built (E4).
- Pass 7 check 3 prints an advisory count of BLOCKED wave-1 steps; not a failure (F16).
- Pass 7 check 4: a step id in a step's `Gaps` cell is an upstream dependency, and depending
  on a BLOCKED step requires BLOCKED (F15). A `Gaps` entry that names neither a pass-4 gap
  id nor a wave-1 step id now fails, naming the step and the fix, instead of being silently
  ignored; the summary counts distinct offending steps, not offender lines.
- Docs and templates: `GAP` is artifact notation, `?` the matrix marker (F3); review of
  report sections 2, 3, 4 and 7, by class through Rules where they apply (F5, F6); `Owner`
  is DEFAULT by rule, producer owns (F7); one register row per field class (F9); externals
  record purpose and interfaces only (F10); commands fold into the acting component (F12);
  line numbering is the reader's, with the tool cited (F13); pass-3 re-entry patches passes
  1-2 forward (F14); rule for resolving a `?` the source is silent on (F17); pass 3's
  done-check leaves `Format`/`Trigger` gaps to pass 4 and the skeleton tests their defaults
  (E1); the runbook's hand pin check loops the pin file, so it verifies every vendored file
  and prints one verdict each, matching CI's pin job (E3).

## 0.1.1 — 2026-09-26

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

## 0.1.0 — 2026-09-26

- First release: the seven-pass system-adoption pipeline, seven templates, the pass-3
  interface matrix (vendored, sha256-pinned) and the pass-7 `check_plan.py` checker.
