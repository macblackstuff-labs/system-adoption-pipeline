# Runbook — system-adoption-pipeline

## Overview

Two on-demand command-line scripts and seven templates; no daemon, no port, no state.
`scripts/interface_matrix.py` (pass 3) is a vendored copy of the one in the
`interface-matrix` skill, pinned by sha256 in `scripts/interface_matrix.UPSTREAM` —
CI fails if the copy no longer matches the pin. `scripts/check_plan.py` (pass 7) is
the deterministic checklist over the filled-in pass 1–6 artifacts. Python 3.9 or newer,
standard library only: no virtualenv, no install step. All paths below are relative to
this skill's own directory.

## Health checks

```bash
python3 scripts/test_check_plan.py
```
Expected: the final line `OK`, exit 0.

`interface_matrix.py` has no test file here — its self-check ships with the
`interface-matrix` skill and is run there; the pin check below is what this skill owns.

```bash
grep -E '^(import|from) ' scripts/check_plan.py scripts/interface_matrix.py
```
Expected: only `argparse`, `graphlib`, `re`, `sys`. A third-party import is a defect.

```bash
grep '^sha256 ' scripts/interface_matrix.UPSTREAM
shasum -a 256 scripts/interface_matrix.py
```
Expected: the two hexadecimal digests are equal. A difference means the vendored pass-3
copy no longer matches its pin — either it was edited here, or it was re-synced from
upstream without updating the pin. The check needs nothing but this skill folder, and CI
runs it on every push. `sha256sum` instead of `shasum -a 256` where that is what the
system has.

`check_plan.py` ends its report with a `counts:` line. `components` and `packages` are
counts of distinct non-blank ids; every other figure — interfaces, gaps, the per-class gap
breakdown in brackets, and wave-1 steps — is a count of table rows. The check 5 figure
above it is neither: it is distinct non-blank USER gap ids plus one per USER row whose `Id`
is blank, `-`, `?`, `none` or `TBD`, since such an id cannot be deduplicated. One
predicate decides "is this a real id" everywhere in the file, so a `-` in a gap's `Id` is
no more a gap than a `-` in a step's `Gaps` cell is a reference to one: check 4 neither
counts it as unresolved nor blocks a step on it.

## Procedures

1. **Start a run.** Copy `assets/templates/` into a working folder and fill the templates in
   order; do not skip a pass's done-check.

2. **Run pass 3.**
   ```bash
   python3 scripts/interface_matrix.py MATRIX-INPUT.md > matrix-report.md
   python3 scripts/interface_matrix.py MATRIX-INPUT.md --sample 0
   python3 scripts/interface_matrix.py MATRIX-INPUT.md --source SOURCE.txt
   ```
   Exit 0 = report written. Exit 1 = a bad input row, named by input line. The input
   format, the report sections and the incident playbook for this script are in the
   `interface-matrix` skill's own runbook.

3. **Run pass 7.**
   ```bash
   python3 scripts/check_plan.py --inventory 01-inventory.md --interfaces 03-interfaces.md \
     --gaps 04-gap-register.md --packages 05-work-packages.md --ordering 06-ordering.md
   ```
   Exit 0 = all five checks passed, 1 = a check failed (offending ids are printed),
   2 = an input file does not hold the table its template defines. Fix in the pass that
   owns the failure, then rerun — never by editing the check.

4. **Change a script.** Add or change a test in `scripts/test_check_plan.py` first and
   watch it fail, then change `scripts/check_plan.py`, then rerun the health checks. If you
   change `scripts/interface_matrix.py`, change it upstream in the `interface-matrix` skill
   first, then copy the new file here and update the `sha256` line in
   `scripts/interface_matrix.UPSTREAM` in the same commit, or CI's pin check fails.

## Incident playbooks

| Symptom | Diagnosis | Fix |
|---|---|---|
| `error: no work package table in FILE (expected columns: wp, components)` (exit 2) | No table in that file carries every required column — usually a renamed header (`Package` for `WP`) or the template's example table deleted along with its header. | Restore the header names. Column order and letter case do not matter; extra columns are ignored. |
| `error: no wave-1 step table in FILE (expected columns: step, wave, components, gaps, blocked, acceptance)` (exit 2) | Same, for pass 6. A Waves table alone does not satisfy it: the Wave 1 steps table carries all six columns. | Add the missing columns to the steps table header. |
| `error: cannot read FILE: ...` (exit 2) | A path is wrong — the checker takes five separate paths and does not guess. | Correct the `--…` path. |
| `check 1 component coverage: FAIL` naming a component | That pass-1 id appears in no package's `Components` cell and no step's. A component outside the boundary is exempt and never named here. Either the 100% rule was broken in pass 5, or the id was renamed in only one artifact. | Put the component in a package, or supersede it in pass 1. Never delete it silently. |
| `check 1b known ids: FAIL — unknown id X` | A package or step names an id the inventory does not have: a typo, or a component invented at packaging time. | Fix the id, or add the component to pass 1 and rerun passes 2–3 for it. A component that first appears in pass 5 was never interface-checked. |
| `check 2 interface endpoints: FAIL — interface IFn has no producer` | The interface row still carries `?` as an endpoint: a missing-component candidate that pass 3 should have resolved. | Resolve it in the matrix input, rerun `interface_matrix.py`, and update pass 3 before rerunning the checker. |
| `check 2 … producer X is in no step` | Both endpoints exist as components, but no wave-1 step builds one of them. A package alone does not satisfy check 2; `external` endpoints are exempt, and a restated id is external only if every one of its pass-1 rows says so. | Name that component in a wave-1 step, or re-cut wave 1 so the interface is exercised. |
| `check 1`/`check 2` names a component you thought was external | The exemption is a token test: the `Type` must begin with the word `external` or carry the token `(external)`, in any letter case. `external`, `External system`, `actor (external)` and `EXTERNAL API` are exempt; `non-external store`, `internal/external bridge`, `external-facing gateway` and `externally reached` are inside the boundary. An id restated on several pass-1 rows is one component, and it is exempt only if every one of its rows says `external`. | If it really is outside the boundary, word the `Type` to start with `external` or to carry `(external)`. Otherwise build it: put it in a package and a wave-1 step. |
| `check 3 wave-1 acceptance: FAIL — no wave-1 step in the ordering` | Pass 6's steps table names no step in wave 1 (a `Wave` cell of `1` or `Wave 1`), so nothing is committed first and check 3 has nothing to verify. | Cut a wave 1: name the first steps and set their `Wave` cell to `1`. |
| `check 3 wave-1 acceptance: FAIL` naming a step | That step's `Acceptance` cell is blank, `-`, `?`, `none` or `TBD` (any letter case). | Write one observable check, or move the step to a later wave, where only package-level acceptance is required. |
| `check 4 wave-1 user gaps: FAIL` | A wave-1 step depends on a USER gap whose `Status` is not `resolved`, and its `Blocked` cell does not say `yes`. | Either get the answer and set the gap to `resolved`, or label the step `yes` in `Blocked` and make sure nothing downstream of it is committed in wave 1. |
| `check 5 user question budget: FAIL — 12 USER question(s), limit 10` | Pass 4 over-classified. The count is of distinct non-blank gap ids plus one per placeholder-id row, so restating one question does not add to it. Most extras are reversible design choices. | Reclassify: adopter-specific, not settled by the source, and irreversible — all three, or it is DEFAULT with a revisit trigger. |
| Checker passes but the plan is obviously wrong | Expected. The checklist sees coverage, not correctness: it cannot know an interface's format is wrong or a default unsafe. | Pass 3's cell-by-cell review and pass 4's class review are the controls, and they are human work. |
| A cell splits into two, or a row is short | An unescaped pipe inside a cell. A backslash escapes the next character; short rows are padded with empty cells, which is why a truncated row usually surfaces as a missing acceptance check. | Escape literal pipes as `\|`. |
| CI fails on the interface-matrix pin check, printing the pinned and the actual sha256 | `scripts/interface_matrix.py` no longer hashes to the `sha256` line in `scripts/interface_matrix.UPSTREAM`: the file was edited here, or re-synced from upstream without updating the pin. | Decide which file is intended. If upstream's is, copy it in and set the pin's `sha256` to the new digest in the same commit; otherwise restore the pinned version from upstream at the path the pin names. Never edit the vendored copy in place. |

## Rollback and recovery

Neither script holds state or writes outside the report you redirect to stdout, so
rollback is a file revert in whatever repository carries the skill folder. The filled-in
pass artifacts are the work worth keeping; reports are disposable and regenerated by
rerunning the scripts against them.

## Escalation

1. A failed check (exit 1): the owner of the failing pass fixes that pass's artifact. No
   escalation — and never by loosening the check.
2. A script defect (exit 2 on a file that does follow the template, or a crash): open an
   issue with the artifact attached, and fix it on a branch with a failing test first.
3. Method disputes — whether a gap is really USER, whether a loop is real, whether the
   walking skeleton is thin enough — are human decisions and belong to the plan's reviewer.
