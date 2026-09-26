# Pass 7 — Verification

Run the deterministic checklist, fix what fails, rerun once, and record both runs.

```bash
python3 scripts/check_plan.py \
  --inventory 01-inventory.md \
  --interfaces 03-interfaces.md \
  --gaps 04-gap-register.md \
  --packages 05-work-packages.md \
  --ordering 06-ordering.md
```

Exit 0 = every check passed. Exit 1 = at least one failed; the offending ids are named.
Exit 2 = a file does not hold the table the template defines, or cannot be read.

Checks 1 and 2 exempt any component that is outside the boundary: its pass-1 `Type` begins
with the word `external` or carries the token `(external)`, in any letter case, so no
package or step builds it. `external`, `External system`, `actor (external)` and
`EXTERNAL API` are exempt; `non-external store`, `internal/external bridge`,
`external-facing gateway` and `externally reached` are inside the boundary and must be
built. An id restated on several pass-1 rows is one component, and it is outside the
boundary only if every one of its rows says `external`. Check 2 requires both endpoints of every
interface to be built by a named wave-1 step, not merely by a package.

## Run 1

```
<paste the output>
```

Fixes made: <what changed in which pass's artifact>

## Run 2

```
<paste the output>
```

## Final counts

<the counts line from run 2, plus anything the checklist cannot see and a human checked>

Done-check: run 2 exits 0, or every remaining failure is recorded with the decision that
accepts it.
