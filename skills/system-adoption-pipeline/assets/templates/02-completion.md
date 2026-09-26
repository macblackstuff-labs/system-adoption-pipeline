# Pass 2 — Component completion

Every component from pass 1 gets its fields filled in and each field marked
SOURCE (with a citation) or SILENT. Never invent a value to remove a SILENT.

Agent components use the source's own job-spec template if it has one; otherwise
the seven fields below. Every other component uses purpose, inputs, outputs, owner,
acceptance.

## Agent components

| Id | Data source | Run schedule | Filters | Expected output | Approval | Metric | Write-back |
|---|---|---|---|---|---|---|---|
| C1 | SOURCE S:L42 | SILENT | SILENT | SOURCE S:L44 | SILENT | SILENT | SOURCE S:L46 |

## Other components

| Id | Purpose | Inputs | Outputs | Owner | Acceptance |
|---|---|---|---|---|---|
| C2 | SOURCE S:L51 | SILENT | SOURCE S:L52 | SILENT | SILENT |

## SILENT count

fields <total> · SILENT <n> · SOURCE <n>

Done-check: every pass-1 id appears exactly once above, every cell reads SOURCE
(with a citation) or SILENT, and the SILENT count is stated.
