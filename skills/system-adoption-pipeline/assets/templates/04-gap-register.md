# Pass 4 — Gap register

Every SILENT field from pass 2 and every interface gap from pass 3 gets exactly one
class. Run passes 1–3 first: adopter questions asked before the tooling has run are
questions the tooling would have answered.

- **SOURCE** — answered elsewhere in the source. Cite it.
- **RESEARCH** — an external fact. Write the exact question; do not research it here.
- **USER** — only the adopter can decide. Adopter-specific, not settled by the source,
  and not a reversible design choice. Everything else is DEFAULT.
- **DEFAULT** — a safe, reversible default exists. State it and the revisit trigger.

At most 10 USER questions, batched in one list, each with a recommended answer.
After this pass defaults are frozen; they change only via their named revisit trigger.

## Gap register

| Id | Gap | Class | Disposition | Status |
|---|---|---|---|---|
| G1 | IF2 format | DEFAULT | markdown file; revisit if a consumer needs a schema | resolved |
| G2 | which accounts to run against | USER | recommended: the adopter's largest segment | open |
| G3 | C1 run schedule | SOURCE | S:L59 says weekly | resolved |
| G4 | rate limit of the external API | RESEARCH | what is the documented per-day limit? | open |

- `Status` is `open` or `resolved`. A USER row stays `open` until the adopter answers;
  pass 7 checks that no wave-1 step depends on an open USER row unless it is BLOCKED.

## USER questions

| Id | Question | Recommended answer |
|---|---|---|
| G2 |  |  |

Done-check: every SILENT field and interface gap has exactly one class; USER rows ≤ 10,
each with a recommended answer; every DEFAULT names its revisit trigger.
