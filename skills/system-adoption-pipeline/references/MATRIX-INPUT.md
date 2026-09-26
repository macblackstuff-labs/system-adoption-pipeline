# Matrix input format — pass 3

The input to `scripts/interface_matrix.py` is one Markdown file with a Components table and
an Interfaces table, plus an optional Rules table. A table is a header row followed by a
`|---|` separator row. A table is read as ours when its header (case-insensitive) shares at
least two names with that table's **required** columns — the optional names (`Class`,
`Status`, `Source`) never count, and the Rules table additionally needs both
`Producer class` and `Consumer class`. Everything else in the file — frontmatter, prose,
other tables — is ignored. Column order does not matter; the header names do.

Once a table is claimed, any missing required column is an error naming it, e.g.
`| Component | Kindx | Notes |` exits 1 with `table at line 3 is missing column(s): kind`.
But a header that keeps **fewer than two** required names is not claimed at all: it is
skipped silently, with no stderr and exit 0. A second components table headed
`| Componnt | Kindd | Class | Notes | Status |` matches only `notes`, so it is dropped —
its rows never reach the matrix and the "second Components table" error never fires.
**After every run, check the report's `components: N` and `specified interfaces: N` counts
against what you wrote.** A count lower than your rows is the only signal that a table was
skipped.

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

- `Kind` blank = internal. The cell must read exactly `external` (letter case ignored) for
  the component to sit outside the boundary and be exempt from the boundary check. A pass-1
  `Type` such as `actor (external)` is **not** external to this script — put the qualifier in
  `Notes` and leave `Kind` as the single word `external`.
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
  naming those attributes. Do not invent a value to make the gap go away.
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

All four columns are required, and a table counts as the Rules table only if its header names
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

Human review reads sections 2, 3, 4 and 7 cell by cell: every missing-component candidate
resolved, every interface gap carried to pass 4, every boundary finding explained, and every
remaining unstated pair either listed as an interface or settled.
