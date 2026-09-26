# Pass 5 — Work packages

Baseline → target. State the baseline explicitly (an empty baseline is a legitimate
assumption, but it is an assumption). Target is the model from passes 1–3.

100% rule: every pass-1 component appears in exactly one package. Pass 7 checks it.

Baseline: <what exists today>
Target: <the model from passes 1–3: N components, M interfaces>

## Packages

| WP | Name | Components | Owner | Inputs | Outputs | Dependencies | Acceptance |
|---|---|---|---|---|---|---|---|
| WP1 | Store substrate | C2 | platform | exports | record files | none | records land and are readable |
| WP2 | Scorer | C1 | platform | record files | scores | WP1 | one score written from real records |

- `Components` is a list of pass-1 ids, separated by spaces or commas.
- `Acceptance` is observable by someone who was not present when the work was done.

Done-check: every component id from pass 1 appears in exactly one row, no row names an
id the inventory does not have, every row has an owner and an acceptance check.
