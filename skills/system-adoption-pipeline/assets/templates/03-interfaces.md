# Pass 3 — Interface matrix

Built by running `scripts/interface_matrix.py` over the matrix input file (two
Markdown tables — Components and Interfaces — plus an optional Rules table; the
format is documented in `references/MATRIX-INPUT.md`). Record here the interface list
the run settled on, with one id per interface, and keep the generated report
next to it.

Matrix input: `<path to the input file>` · report: `<path to the report>`

## Interfaces

| Id | Producer | Consumer | Flows | Format | Trigger | Owner | Source |
|---|---|---|---|---|---|---|---|
| IF1 | C2 | C1 | raw event rows | ndjson file | nightly | platform | S:L42 |
| IF2 | C1 | H1 | weekly digest | GAP | GAP | C1 | S:L60 |

- `Producer`/`Consumer` are pass-1 ids. `?` means the endpoint is a missing-component
  candidate: resolve it in the matrix input and rerun before this pass is done.
- A blank or `GAP` in Flows/Format/Trigger is an interface gap and goes to pass 4. `Owner` is
  producer-by-default (below), so it is filled here rather than carried.
  `GAP` is this artifact's notation only: in the matrix input an unknown is a blank cell or
  `?`, and `GAP` there is an ordinary value that settles the cell.
- `Owner` is DEFAULT by rule: the producer owns what it emits unless the source says
  otherwise. Write the producer's id and record the rule once in pass 4, not per interface.
- `Format` and `Trigger` may stay `GAP` here; each one is carried to pass 4, and the walking
  skeleton is where the defaults pass 4 gives them are first tested.

## Findings carried to pass 4

| Finding | Id | What is missing |
|---|---|---|
| interface gap | IF2 | format, trigger |

Done-check: the matrix run exits 0, has no missing-component candidates and no
unexplained boundary findings, the human review of sections 2, 3, 4 and 7 of its report
is done (section 7 may be reviewed by class, through the Rules table), and every remaining
gap is listed here — none of them need be filled in this pass.
