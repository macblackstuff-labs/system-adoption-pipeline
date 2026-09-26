# Pass 3 — Interface matrix

Built by running `scripts/interface_matrix.py` over the matrix input file (two
Markdown tables — Components and Interfaces — plus an optional Rules table; the
format is documented in that script's own skill). Record here the interface list
the run settled on, with one id per interface, and keep the generated report
next to it.

Matrix input: `<path to the input file>` · report: `<path to the report>`

## Interfaces

| Id | Producer | Consumer | Flows | Format | Trigger | Owner | Source |
|---|---|---|---|---|---|---|---|
| IF1 | C2 | C1 | raw event rows | ndjson file | nightly | platform | S:L42 |
| IF2 | C1 | H1 | weekly digest | GAP | GAP | GAP | S:L60 |

- `Producer`/`Consumer` are pass-1 ids. `?` means the endpoint is a missing-component
  candidate: resolve it in the matrix input and rerun before this pass is done.
- A blank or `GAP` in Flows/Format/Trigger/Owner is an interface gap and goes to pass 4.

## Findings carried to pass 4

| Finding | Id | What is missing |
|---|---|---|
| interface gap | IF2 | format, trigger, owner |

Done-check: the matrix run exits 0, has no missing-component candidates and no
unexplained boundary findings, the human review of section 3 of its report is done,
and every remaining gap is listed here.
