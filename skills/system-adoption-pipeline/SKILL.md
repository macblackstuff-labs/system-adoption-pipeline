---
name: system-adoption-pipeline
description: "Turns a narrative description of a large system — a transcript, a talk, a book chapter, a competitor teardown — into an ordered, gap-closed implementation plan, through seven passes: extract, complete, interface matrix, gap register, work packages, ordering, deterministic verification. Use when adopting somebody else's system of roughly eight or more components, when a plan is called too high-level or too vague, when a build plan must be provably complete against its source before work starts, or when someone brings only a goal for a system of that size and needs it turned into a complete plan."
license: MIT
compatibility: Requires Python 3.9 or newer; standard library only, no third-party packages and no network access.
---

# system-adoption-pipeline

Seven passes, in order. Each pass has one input, one output artifact, and a done-check.
Do not start a pass before the previous one's done-check holds: an interface found after
the packages are cut re-opens the packaging, and an adopter question asked before the
matrix has run is a question the matrix would have answered.

Requirements: Python 3.9 or newer, standard library only. All `scripts/...` and
`assets/templates/...` paths below are relative to this skill's own directory, and
`references/RUNBOOK.md` is the operating runbook for the two scripts. Copy each template
into your working folder and fill it in; keep the filled artifacts together, because
passes 4, 5, 6 and 7 all read the earlier ones.

## The seven passes

| # | Pass | Input | Output artifact | Done-check |
|---|---|---|---|---|
| 1 | Extract | the narrative source, numbered by the reader (`nl -ba`) | `assets/templates/01-inventory.md` | every component has an id, a type, a one-line purpose and a source citation; every uncertainty is a hot spot |
| 2 | Complete | pass 1 inventory | `assets/templates/02-completion.md` | every field is marked SOURCE (cited) or SILENT; the SILENT count is stated |
| 3 | Interface matrix | pass 1 inventory (and pass 2's declared inputs/outputs) | `assets/templates/03-interfaces.md` plus the generated report | the matrix run exits 0, no missing-component candidates, no unexplained boundary findings, human review of report sections 2, 3, 4 and 7 done, every remaining `Format`/`Trigger` gap carried to pass 4 (they need not be filled here; `Owner` is producer-by-default, so it never remains) |
| 4 | Gap register | every pass-1 hot spot, every SILENT field and every interface gap | `assets/templates/04-gap-register.md` | each gap has exactly one class; USER questions ≤ 10, each with a recommended answer; every DEFAULT names its revisit trigger |
| 5 | Work packages | passes 1–3 | `assets/templates/05-work-packages.md` | every component in exactly one package; every package has an owner and an acceptance check |
| 6 | Ordering | pass 5 | `assets/templates/06-ordering.md` | walking skeleton named; wave 1 decomposed to atomic steps, one acceptance check each; later waves at package level, and every component of a later wave named by its package |
| 7 | Verification | passes 1, 3, 4, 5, 6 | `assets/templates/07-verification.md` | `scripts/check_plan.py` exits 0, or every remaining failure carries the decision that accepts it |

## Starting from a goal

The pipeline reads a written source, so a request that is only a goal gets one written
first. Interview the goal owner — what the system is for, who and what it touches, what
already exists, what must not change, what "done" looks like — and write the answers up
as a spec with numbered lines. That spec is the pass-1 source, cited like any transcript.

The plan is then only as complete as the spec: a plan cannot be more complete than the
document it was extracted from. Every hot spot in pass 1 and every SILENT field in pass 2
is a gap in the spec, not a gap in the pipeline — take each one back to the owner as a
question, add the answer to the spec, and re-run the pass.

A goal with fewer than roughly eight components does not need this: decompose it directly
into steps and skip the seven passes.

## Pass 1 — Extract

Number the source's lines yourself — sources rarely carry numbers — with
`nl -ba SOURCE.txt`, and name that tool in the inventory's `Source:` line so every citation
can be reproduced. Extract, Event Storming style: actors, domain events, commands,
policies, read models, external systems. A command folds into the purpose of the component
that acts on it; events, policies and read models are rows of their own. Cite the line for
every component. Anything the source leaves uncertain becomes a hot spot, never a guess.

## Pass 2 — Complete

Fill in every component's fields. If the source carries its own specification template
for a kind of component (a job spec, a service template), use that template's own fields
for those components; everything else gets purpose, inputs, outputs, owner, acceptance.
A component outside the boundary (pass-1 `Type` external) records only its purpose and its
interfaces; its other fields are N/A, not SILENT, because nobody builds it.
Mark each field SOURCE with a citation or SILENT. Report the SILENT count — it is the
size of the gap register before pass 3 adds to it.

## Pass 3 — Interface matrix

For every ordered pair of components that exchanges anything, record what flows, in what
format, on what trigger, and which component owns the artefact crossing the boundary.
Owner is DEFAULT by rule: the producer owns what it emits unless the source says otherwise,
so write the producer in `Owner` and record the rule once in pass 4 — not one gap per
interface. Do not do this by hand and do not let a model generate the matrix: run the script.

```bash
python3 scripts/interface_matrix.py MATRIX-INPUT.md > matrix-report.md
python3 scripts/interface_matrix.py MATRIX-INPUT.md --sample 0
python3 scripts/interface_matrix.py MATRIX-INPUT.md --source SOURCE.txt
```

The input is one Markdown file with a Components table and an Interfaces table, plus an
optional Rules table (`Producer class | Consumer class | Disposition | Reason`) that
settles unstated pairs a class at a time — `none` takes those pairs out of review,
`review` keeps them, and an explicit row always beats a rule. `--sample 0` prints every
unstated pair; `--source FILE` lists the source lines nothing cites, which is where an
unmodelled component hides. The input format, the ten report sections and the four that
human review must read (2, 3, 4 and 7) are documented in `references/MATRIX-INPUT.md`.
Review by class is compliant: at scale, Rules are the intended instrument for settling
unstated pairs, and a reviewer reads each rule and its reason instead of every cell it
settles.
`scripts/interface_matrix.py` and its self-check `scripts/test_interface_matrix.py` are
vendored copies; `scripts/interface_matrix.UPSTREAM` names the upstream repo, the path of
each file within it, and the sha256 of each copy shipped here. The repository's CI pin
job fails if a copy no longer matches its pin (`references/RUNBOOK.md` has the same check to
run by hand), so re-syncing is a deliberate act — copy the upstream files in and
update their sha256 lines in the pin file in the same commit.

Rerun until there are no missing-component candidates. Where the source is silent about a
`?` endpoint, resolve it to the component the row's citation names and class that choice
DEFAULT in pass 4, or drop the row and record it as a pass-1 hot spot. When a finding here
(an uncited `--source` span, a missing component) shows pass 1 or 2 was incomplete, patch
those artifacts forward — add the row, note that pass 3 found it — rerun the matrix and carry
on; do not restart the pipeline from pass 1. Then write the settled interface
list into `assets/templates/03-interfaces.md` with one id per interface, and carry every
remaining gap to pass 4.

## Pass 4 — Gap register

Every pass-1 hot spot, every SILENT field and every interface gap gets exactly one class.
Fields that share one answer may share one row: a register row per field class (for example
"`Owner` of every interface = its producer") with the rule stated, rather than one row per
field.
A hot spot leaves this pass either as a register row or closed with a stated reason — pass
1's hot spots are what this pass reads, so none of them may simply be dropped.

- **SOURCE** — answered elsewhere in the source. Cite the line.
- **RESEARCH** — an external fact. Write the exact question. Do not research it in this pass.
- **USER** — only the adopter can decide. All three must hold: it is adopter-specific,
  it is not settled by the source, and it is not a reversible design or modelling choice.
  A reversible choice is DEFAULT, not USER.
- **DEFAULT** — a safe, reversible default exists. State the default and the trigger that
  would revisit it.

Prefer DEFAULT over USER whenever the choice is reversible. At most 10 USER questions,
batched in one list, each with a recommended answer. Ask them only now, after passes 1–3
have run. After this pass, defaults are frozen and change only via their revisit trigger.

## Pass 5 — Work packages

Baseline → target, with the baseline stated as an assumption when the adopter's starting
point is unknown. Apply the WBS 100% rule: every component from pass 1 in exactly one
package. Each package gets owner role, inputs, outputs, dependencies and an acceptance
check that someone who was not present can observe.

## Pass 6 — Ordering

First the walking skeleton: the thinnest end-to-end slice that exercises every layer of
the system once, chosen to prove the data contracts pass 3 left as gaps and pass 4
settled by default — the skeleton is where those defaults are first tested. Then expand
system by system in dependency order. Rolling wave: wave 1 decomposed to atomic steps —
verb-led, ≤2 hours, exactly one acceptance check, no open decision embedded — later waves
at package level, decomposed when the preceding wave ends. Note the feedback loops the
order must respect; a loop that closes at a recurring review is not a build-order
dependency.

## Pass 7 — Verification

```bash
python3 scripts/check_plan.py \
  --inventory 01-inventory.md \
  --interfaces 03-interfaces.md \
  --gaps 04-gap-register.md \
  --packages 05-work-packages.md \
  --ordering 06-ordering.md
```

Five checks: every component has at least one package or step; every interface has both
endpoints covered by the plan — some package or some step, so a later-wave interface passes
(a plan with packages but no wave-1 steps fails check 3, which is where that belongs); an
endpoint id the inventory does not know fails check 2 as a pass-3 defect, and an interface
between two externals builds nothing, so it is exempt and not counted as built;
every wave-1 step has an acceptance check, with an advisory line (not a failure) counting
the wave-1 steps labelled BLOCKED; no wave-1 step depends on an unresolved USER gap, or on a
BLOCKED wave-1 step named by its step id in the `Gaps` cell, unless it is labelled BLOCKED;
every `Gaps` entry names a real gap id or a wave-1 step id;
USER questions ≤ 10, counted as distinct non-blank
USER gap ids plus one per USER row whose id is blank or a placeholder (`-`, `?`,
`none`, `TBD`). Exit 0 = all passed, 1 = a check
failed and the offending ids are named, 2 = a file does not hold the table its template
defines. A component is outside the boundary when its pass-1 `Type` begins with the word
`external` or carries the token `(external)`, in any letter case: checks 1 and 2 exempt it,
as a component and as an interface endpoint. `external`, `External system`,
`actor (external)` and `EXTERNAL API` are exempt; `non-external store`,
`internal/external bridge`, `external-facing gateway` and `externally reached` are inside
the boundary and must be built. An id restated on several pass-1 rows is one component, and
it is outside the boundary only if every one of its rows says `external`: one row that does
not, and it is ours to build. Fix the failures in
the pass that owns them, rerun once, and record both runs
with the final counts. Self-check for the checker itself:
`python3 scripts/test_check_plan.py`.

The checklist is not the review. It cannot tell you that an interface is wrong, only that
nobody builds it — the review of report sections 2, 3, 4 and 7 in pass 3 and the
class-by-class review in pass 4 are human work and are not delegable to another model pass.
