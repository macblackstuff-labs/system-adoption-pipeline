# Matrix input format — pass 3

The input to `scripts/interface_matrix.py` is one Markdown file with a Components table and
an Interfaces table, plus an optional Rules table. A table is a header row followed by a
`|---|` separator row. A table is read as ours when its header (case-insensitive) shares at
least two names with that table's **required** columns — a table's own optional names never
count (`Class` and `Status` in Components, `Source` and `Status` in Interfaces, `Status` in
Rules), and the Rules table additionally needs both
`Producer class` and `Consumer class`. Everything else in the file — frontmatter, prose,
other tables — is ignored. Column order does not matter; the header names do.

Once a table is claimed, any missing required column is an error naming it, e.g.
`| Component | Kindx | Notes |` exits 1 with `table at line 3 is missing column(s): kind`.
But a header that keeps **fewer than two** required names is not claimed at all, and its
whole table is skipped. If two or more of its cells are near-miss spellings of one table's
required names, the skip is announced on stderr and the exit code is unchanged:
`warning: line N: table header misspells a Components, Interfaces or Rules column set; the
whole table was ignored`. A second components table headed
`| Componnt | Kindd | Class | Notes | Status |` matches only `notes`, so it is dropped with
that warning (exit 0): its rows never reach the matrix and the "second Components table"
error never fires. The same holds for a misspelled Interfaces table
(`| Producr | Consumr | Flws | … |`) and for a Rules table whose class columns are misspelled
(`| Producer class | Consumr class | … |`). If the misspelled table is the file's *only* one
of its kind, the warning is followed by `error: no Components table found (expected columns:
component, kind, notes)` (likewise for Interfaces) and exit 1. A genuinely foreign table
(`| Fruit | Colour |`, `| Disposition | Reason |`) is skipped silently. Which diagnostic a
misspelling gets depends on the exact-name count, not on how bad it is: `| COMPONNT | Kind |
Notes |` still shares two exact names, so it is claimed and exits 1 with
`table at line 3 is missing column(s): component` (the line the header is on).
Synonyms (`From` for `Producer`) are not
near misses: a table of them is skipped with no warning, so the reconciliation below is
still the check that catches it.

**After every run, reconcile the report's section 1 counts against your own row counts.**
Retired and unresolved rows are counted separately, so the sums are what must match, not
`components: N` alone:

- Components rows = `components: N` + the components figure in `superseded rows: N (interfaces I, components C)`.
- Interfaces rows = `specified interfaces: N` + `interfaces with gaps: N` + `explicit none: N` + `missing-component candidates: N` + the interfaces figure in `superseded rows:`.

A sum below the rows you wrote means a table (or row) was dropped — look first for a
`warning:` line on stderr. With `--source`, a dropped
row's `S:Lnn` citations also resurface in section 10 as uncited spans.

```markdown
## Components

| Component | Kind | Class | Notes | Status |
|---|---|---|---|---|
| Ingest |  | ING | pulls raw events (S:L42) |  |
| Analyst | external |  | a human, outside the system boundary |  |

## Interfaces

| Producer | Consumer | Flows | Format | Trigger | Owner | Source | Status |
|---|---|---|---|---|---|---|---|
| Ingest | Store | raw event rows | ndjson file | nightly cron | platform | S:L42 |  |
| Ingest | Scorer | none |  |  |  |  |  |
| ? | Analyst | weekly digest | ? | ? | ? |  |  |
```

## Components

Required columns: `Component`, `Kind`, `Notes`. Optional: `Class`, `Status`.

- `Kind` blank = internal. A component sits outside the boundary, exempt from the boundary
  check, when its `Kind`'s first word is `external` or it carries the token `(external)`,
  in any letter case — the same rule pass 7's `check_plan.py` applies to a pass-1 `Type`, so
  the `Type` can be copied into `Kind` unchanged. `External system` and `actor (external)` are
  external; `externalize`, `non-external store` and `(externalish)` are internal.
- `Class` is optional and free-form (`ING`, `AGT`); it only feeds the Rules table. A blank
  `Class` matches no rule, not even `*`, so a forgotten cell can never drop pairs from review
  — report section 9 names every unclassed component.
- A duplicate active component name exits 1. A `Status` beginning `superseded` retires the
  row; a retired name may be re-declared later.
- One Components table per file. A second one exits 1, naming both header lines — addenda go
  in the first table, below its existing rows.

## Interfaces

Required columns: `Producer`, `Consumer`, `Flows`, `Format`, `Trigger`, `Owner`. Optional:
`Source`, `Status`.

- **List every ordered pair that exchanges anything.** A pair left out is an unstated pair,
  not a "no".
- `Flows` = `none` declares there is deliberately no interface for that ordered pair.
- Any of `Flows`/`Format`/`Trigger`/`Owner` left blank or `?` makes the row an interface gap
  naming those attributes. Do not invent a value to make the gap go away. `Owner` is the
  exception by rule: the producer owns what it emits unless the source says otherwise, so
  write the producer there (the rule is one DEFAULT row in pass 4).
- The gap markers this script reads are the empty cell and `?` — nothing else. `GAP` is
  pass-3 **artifact** notation for `assets/templates/03-interfaces.md`; in the matrix input it
  is an ordinary value and settles the cell.
- `?` as `Producer` or `Consumer` makes the row a missing-component candidate: kept out of the
  graph and listed for you to resolve.
- Cite the source for every cell you can (`S:Lnn`, doc path, ticket). An uncited cell is a
  claim the reviewer has to re-derive.
- A `Status` beginning `superseded` retires the row.
- One Interfaces table per file. A second one exits 1, naming both header lines — addenda go
  in the first table, below its existing rows.

## Rules (optional)

```markdown
## Rules

| Producer class | Consumer class | Disposition | Reason |
|---|---|---|---|
| ING | AGT | none | ingest never calls an agent |
| AGT | * | review | look at every agent output |
```

All four columns are required; `Status` is optional, and a `Status` beginning `superseded`
retires the rule (its `Reason` citations are still range-checked). A table counts as the
Rules table only if its header names
both `Producer class` and `Consumer class`, so a foreign `| Disposition | Reason |` table is
left alone. A `none` rule settles every unstated pair whose producer and consumer classes
match (`*` = any classed component): not listed, not sampled. `review` wins where both match,
and an explicit interface row or a `Flows` = `none` row always beats a rule. An unknown
`Disposition`, or a class no component has, exits 1.

## Citations and `--source`

Every `L<n>`, `L<a>-<b>` and `L7,11-12` in any cell of any active Components or Interfaces row
counts as a cited source line. A Rules row's `Reason` justifies the rule and models nothing,
and a superseded row models nothing any more, so their citations cover no line — they are
still range-checked. `--source FILE` reports the uncited lines as contiguous spans, which is
where an unmodelled component or interface hides. A citation past the file's last line exits 1,
as does `L0` (source lines start at 1); both need `--source` to be caught. A reversed range
such as `L9-7` exits 1 while parsing, with or without `--source`.

## Cells

A backslash escapes the next character and is dropped: `\|` is a literal pipe inside a cell,
`\\` is a literal backslash and leaves the next `|` a delimiter (`C:\\| csv` is `C:\` then
`csv`). A `|` line outside any table is ignored with a warning on stderr.

## The report's sections

1. Summary · 2. Missing-component candidates · 3. Interface gaps · 4. Boundary check ·
5. Feedback loops · 6. Partitioned order · 7. Unstated pairs · 8. Matrix ·
9. Class rules (only with a Rules table) · 10. Source coverage (only with `--source`).

Human review reads sections 2, 3, 4 and 7: every missing-component candidate resolved,
every interface gap carried to pass 4, every boundary finding explained, and every remaining
unstated pair either listed as an interface or settled. Section 7 may be reviewed by class:
at scale a Rules table is the intended instrument, and reading each rule and its reason in
section 9 is compliant review of the pairs it settles. Only pairs no rule settles are read
one by one.

## The review ledger and certification

Human review is written into a ledger, and `--certify` checks it. The ledger is one
Markdown file kept beside the input, holding one disposition table:

```markdown
| Kind | Finding | Disposition | Reason | Reviewer | Date | Fingerprint |
|---|---|---|---|---|---|---|
```

One row per finding, keyed by identity rather than input line, because lines move when the
input is edited. `Kind` is one of `candidate`, `gap`, `boundary`, `pair`, `span`; the
`Finding` cell carries the identity — candidates and gaps read `producer -> consumer:
flows`, unstated pairs `A -> B`, boundary findings the component's name, uncited spans
`L7-9@<source sha256>`. `Reviewer` is the reviewer of record and `Date` when it reviewed;
`Fingerprint` pins the content dispositioned — a certification record's blocker lines carry
the current fingerprints to paste. Every cell but `Reason` is required. The reviewer of
record must be someone other than whatever drafted the input: an independent human reviewer
by default, a model only when the user explicitly pinned one.

```bash
python3 scripts/interface_matrix.py MATRIX-INPUT.md --certify MATRIX-INPUT.ledger.md
```

Start the ledger as nothing but the header row and certify once: every finding the report
derives from the input comes back an `unreviewed:` blocker, named by identity and carrying
its current fingerprint, so the refusal record doubles as the review worksheet. Certify
with `--source` when the input cites one, or the uncited spans never enter review. An entry
covers the finding whose identity it names when its fingerprint matches; the disposition
text is the reviewer's judgment. Certification exits 0 when every finding is dispositioned
and none has drifted — that is pass 3's completion — and exit 3 names every blocker:
`drifted:` an entry whose finding is gone from the input or changed since disposition,
`unreviewed:` a finding no entry covers. Every gap dispositioned with a `Disposition`
starting `open` — `open-parked` is the gap you are not filling now — is listed in the
record as an advisory, never a blocker: parked, not ignored. Under `--certify`, two active
input rows sharing one `producer -> consumer: flows` identity also exit 1 (the ledger
cannot tell them apart), as do the ledger's own bad rows: wrong width, unknown kind, a
missing required cell, a duplicate identity, a second disposition table. Every run writes
a record beside the ledger, `<ledger>.cert.md`, and prints it instead of the report: the
input, report and (when `--source` ran) source file bound by sha256, the gate result,
every blocker and advisory, and the effective flags, which a later certification must
replay exactly. A pass also stamps the same record into the ledger as its
`## Certification record` section, replacing the section a previous pass stamped. The
finished deliverable is four files shipped together: the report, its certification record,
the input, and the ledger — enough for any consumer to re-run certification and check the
record's sha256 bindings against the files they were sent.
