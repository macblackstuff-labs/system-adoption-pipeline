# system-adoption-pipeline

An Agent Skill for Claude Code, Codex, Cursor and any harness that reads `skills/` from
disk: it turns a narrative description of a system into an ordered, gap-closed
implementation plan — requirements analysis, system design review via an interface matrix,
gap register, work breakdown structure and build order — and verifies the plan deterministically.

## What it does

The input is a written source that describes somebody else's system: a transcript, a talk,
a book chapter, a competitor teardown, or a numbered spec written from an interview. The
source is read line by line and every component in it is extracted with a citation.

Seven passes follow, each with one input, one output artifact and a done-check: extract,
complete, interface matrix, gap register, work packages, ordering, deterministic
verification. Two of the passes are scripts rather than model output — pass 3 builds the
interface matrix, pass 7 runs the checklist over the filled-in artifacts — so the parts
that must be exhaustive are computed, not generated.

The output is seven Markdown artifacts in a working folder: an inventory, a completion
sheet, an interface list, a gap register, work packages, a build order, and a verification
record. A plan is finished when `scripts/check_plan.py` exits 0, or when every remaining
failure carries the decision that accepts it.

## Who it is for

Engineers, architects and technical leads who have to adopt a system of roughly eight or
more components that somebody else designed, and who need the build plan to be provably
complete against its source before work starts — typically after a plan has been called
too high-level or too vague, or when only a goal exists and it has to become a plan.

## Example

Save the block below as `MATRIX-INPUT.md` inside the installed skill folder. It is a
minimal pass-3 input, in the format `references/MATRIX-INPUT.md` documents — a Components
table and an Interfaces table:

```markdown
## Components

| Component | Kind | Class | Notes | Status |
|---|---|---|---|---|
| Ingest |  | ING | pulls raw events (S:L42) |  |
| Store |  | STO | holds raw events (S:L44) |  |
| Analyst | external |  | a human, outside the system boundary |  |

## Interfaces

| Producer | Consumer | Flows | Format | Trigger | Owner | Source | Status |
|---|---|---|---|---|---|---|---|
| Ingest | Store | raw event rows | ndjson file | nightly cron | platform | S:L42 |  |
| Store | Analyst | weekly digest | ? | ? | ? | S:L44 |  |
```

Then run, from that same folder:

```bash
python3 scripts/interface_matrix.py MATRIX-INPUT.md
```

The report opens with the counts and the findings a reviewer reads:

```markdown
# Interface matrix report

## 1. Summary

- components: 3 (2 internal, 1 external)
- specified interfaces: 1
- interfaces with gaps: 1
- explicit none: 0
- missing-component candidates: 0
- unstated pairs: 4
- feedback loops: 0
- self-dependencies: 0
- superseded rows: 0 (interfaces 0, components 0)

## 3. Interface gaps

| line | producer | consumer | missing |
|---|---|---|---|
| line 14 | Store | Analyst | Format, Trigger, Owner |
```

Eight sections in all here, ending at `## 8. Matrix`, the N² matrix itself; sections 9 and
10 are conditional — a Rules table adds one, `--source` the other. The gap row above is what
pass 4 turns into a register entry. And the report is not pass 3's end: its findings are
reviewed into a ledger and the matrix is certified against it —
[Certifying the reviewed matrix](#certifying-the-reviewed-matrix) below.

## Install

| Harness | Command | Notes |
|---|---|---|
| skills CLI | `npx skills add macblackstuff/system-adoption-pipeline` | Prompts for the agents to install into. |
| Claude Code | `npx skills add macblackstuff/system-adoption-pipeline -a claude-code -y` | Verified in CI. |
| Codex | `npx skills add macblackstuff/system-adoption-pipeline -a codex -y` | Verified in CI. |
| Cursor | `npx skills add macblackstuff/system-adoption-pipeline -a cursor -y` | Verified in CI. |
| Any harness that reads `skills/` from disk | Copy [`skills/system-adoption-pipeline`](skills/system-adoption-pipeline) into where your agent reads skills from | Every path inside the skill is relative to its own folder, so the destination does not matter. |

The [`skills` CLI](https://github.com/vercel-labs/skills) covers 79 agents in all, and CI
installs and tests every one of them the same way — see [Harnesses tested](#harnesses-tested).

Verify any copy with its self-check, run from inside the installed skill folder:

```bash
python3 scripts/test_check_plan.py    # expected: final line OK, exit 0
```

## Usage

Ask the agent in its own words — the skill's description triggers on adopting somebody
else's system of roughly eight or more components, on a plan called too high-level or too
vague, on a build plan that must be provably complete against its source before work
starts, and on a goal for a system of that size that has to become a complete plan. For
example: "adopt the system in this transcript and give me an ordered build plan".

The two scripts also run directly. Pass 3 runs from wherever the input file sits — from
inside the skill folder, with the `MATRIX-INPUT.md` above saved there:

```bash
python3 scripts/interface_matrix.py MATRIX-INPUT.md > matrix-report.md
```

### Certifying the reviewed matrix

Pass 3 does not end at the report. Its findings are reviewed into a ledger kept beside the
input, and the matrix is certified against it:

```bash
python3 scripts/interface_matrix.py MATRIX-INPUT.md --certify MATRIX-INPUT.ledger.md
```

The ledger is one table, `Kind | Finding | Disposition | Reason | Reviewer | Date |
Fingerprint`, one row per finding, keyed by identity rather than input line. Start it as
nothing but the header row and certify once: every finding comes back an `unreviewed:`
blocker carrying its current fingerprint, so the refusal record doubles as the review
worksheet. Disposition each finding — the fingerprints to paste are in the record — and
certify again. Exit 0 writes `MATRIX-INPUT.ledger.cert.md` beside the ledger: the
certification record, binding the input, the report and (under `--source`) the source file
by sha256, plus the flags the review ran under, which every later certification must
replay exactly. Exit 3 is the refusal, every blocker — a drifted or unreviewed finding —
named in the record. The finished deliverable is the report, its certification record, the
input, and the ledger — plus the source file when the review ran under `--source` — enough
for any consumer to re-run
certification. The reviewer of record must be someone other than whatever drafted the
input: an independent human by default, a model only when one is explicitly pinned. The
ledger format and the review duties are in
[`references/MATRIX-INPUT.md`](skills/system-adoption-pipeline/references/MATRIX-INPUT.md).

Pass 7 runs from the folder holding the filled-in artifacts. The shipped templates are
already a passing example, so this is the command CI runs, from
`assets/templates` inside the skill folder:

```bash
python3 ../../scripts/check_plan.py \
  --inventory 01-inventory.md \
  --interfaces 03-interfaces.md \
  --gaps 04-gap-register.md \
  --packages 05-work-packages.md \
  --ordering 06-ordering.md
```

## How it works

Each pass writes one artifact from a template, and no pass starts before the previous
done-check holds.

1. **Extract** — number the source's lines, extract every component with a citation, record every uncertainty as a hot spot.
2. **Complete** — fill each component's fields, marking every one SOURCE (cited) or SILENT, and state the SILENT count.
3. **Interface matrix** — `scripts/interface_matrix.py` builds the N² matrix (a design structure matrix) and reports missing components, interface gaps, unconsumed outputs, feedback loops and never-stated pairs; once its findings are reviewed into a ledger, it certifies the review (`--certify`). Input format and its up to ten sections (two conditional): [`references/MATRIX-INPUT.md`](skills/system-adoption-pipeline/references/MATRIX-INPUT.md).
4. **Gap register** — every hot spot, SILENT field and interface gap gets exactly one class: SOURCE, RESEARCH, USER or DEFAULT. At most 10 USER questions.
5. **Work packages** — the WBS 100% rule: every component in exactly one package, each with an owner and an observable acceptance check.
6. **Ordering** — walking skeleton first, then rolling wave: wave 1 decomposed to atomic steps, later waves at package level.
7. **Verification** — `scripts/check_plan.py` runs five checks over the artifacts of passes 1, 3, 4, 5 and 6.

Operating the two scripts — health checks, procedures, incident playbooks — is
[`references/RUNBOOK.md`](skills/system-adoption-pipeline/references/RUNBOOK.md). The pass
definitions themselves are [`SKILL.md`](skills/system-adoption-pipeline/SKILL.md).

## Output format

| Artifact | Template | Holds |
|---|---|---|
| Inventory | [`01-inventory.md`](skills/system-adoption-pipeline/assets/templates/01-inventory.md) | Every component: id, type, purpose, source citation, hot spots. |
| Completion | [`02-completion.md`](skills/system-adoption-pipeline/assets/templates/02-completion.md) | Each component's fields, marked SOURCE or SILENT. |
| Interfaces | [`03-interfaces.md`](skills/system-adoption-pipeline/assets/templates/03-interfaces.md) | The settled interface list, one id per interface. |
| Gap register | [`04-gap-register.md`](skills/system-adoption-pipeline/assets/templates/04-gap-register.md) | Every gap with its class, recommended answer or revisit trigger. |
| Work packages | [`05-work-packages.md`](skills/system-adoption-pipeline/assets/templates/05-work-packages.md) | Packages with owner, inputs, outputs, dependencies, acceptance. |
| Ordering | [`06-ordering.md`](skills/system-adoption-pipeline/assets/templates/06-ordering.md) | Walking skeleton, wave 1 atomic steps, later waves. |
| Verification | [`07-verification.md`](skills/system-adoption-pipeline/assets/templates/07-verification.md) | The check_plan runs and their final counts. |

`scripts/interface_matrix.py` writes its report to stdout; `scripts/check_plan.py` exits 0
when every check passes, 1 when a check fails (naming the offending ids), and 2 when a file
does not hold the table its template defines.

## Requirements and limits

Python 3.9 or newer. Standard library only — no dependencies, no virtualenv, no install
step, and the scripts make no network calls.

A system of fewer than roughly eight components does not need this — decompose it directly
into steps. The plan is only as complete as its source: a hot spot or a SILENT field is a
gap in the source document, not something the pipeline can fill. And the checklist is not
the review — it can tell you that nobody builds an interface, never that the interface is
wrong. Report sections 2, 3, 4 and 7 in pass 3, and the class-by-class review in pass 4,
are human work.

## Related

- [interface-matrix](https://github.com/macblackstuff/interface-matrix) — the sibling skill that pass 3 vendors; use it on its own when you only need the matrix.
- [Agent Skills specification](https://agentskills.io/specification) — the format this skill is written to.

## Harnesses tested

CI installs the skill with the `skills` CLI on every push and pull request, once per agent in its
own throwaway home, and runs the skill's own self-tests from each installed copy. Every agent the
CLI supports is covered — 79 agents with `skills` 1.7.0 — and the list is read from the CLI at run
time, so agents added by a future CLI release are tested automatically without editing this repo.

Two of the 79 are documented exceptions, listed in
[`.github/scripts/smoke-install.sh`](.github/scripts/smoke-install.sh): `eve` and `promptscript`,
which the CLI reports do not support global skill installation. Every other agent must install and
pass, so nothing is silently skipped; the job ends with a `<N> of <M> agents installed and tested`
line.

Many agents share a user-level skills directory, so on a real machine one installed copy serves all
of them. CI still installs and tests each agent separately, so a change to any one agent's target
is caught. The targets, from a real run:

| Global install path (under `~`) | Agents |
|---|---|
| `.agents/skills/` | `amp`, `antigravity`, `antigravity-cli`, `cline`, `codex`, `cursor`, `deepagents`, `dexto`, `droid`, `firebender`, `gemini-cli`, `github-copilot`, `kilo`, `kimi-code-cli`, `loaf`, `opencode`, `replit`, `sarvam-code`, `universal`, `warp`, `zed` |
| `.zencoder/skills/` | `zencoder`, `zenflow` |
| `.adal/skills/` | `adal` |
| `.aider-desk/skills/` | `aider-desk` |
| `.astrbot/data/skills/` | `astrbot` |
| `.augment/skills/` | `augment` |
| `.autohand/skills/` | `autohand-code` |
| `.bob/skills/` | `bob` |
| `.claude/skills/` | `claude-code` |
| `.codeartsdoer/skills/` | `codearts-agent` |
| `.codebuddy/skills/` | `codebuddy` |
| `.codeium/windsurf/skills/` | `windsurf` |
| `.codemaker/skills/` | `codemaker` |
| `.codestudio/skills/` | `codestudio` |
| `.commandcode/skills/` | `command-code` |
| `.config/crush/skills/` | `crush` |
| `.config/devin/skills/` | `devin` |
| `.config/goose/skills/` | `goose` |
| `.config/kimchi/harness/skills/` | `kimchi` |
| `.continue/skills/` | `continue` |
| `.forge/skills/` | `forgecode` |
| `.fx/skills/` | `fx` |
| `.grok/skills/` | `grok` |
| `.hermes/skills/` | `hermes-agent` |
| `.iflow/skills/` | `iflow-cli` |
| `.inferencesh/skills/` | `inference-sh` |
| `.jazz/skills/` | `jazz` |
| `.junie/skills/` | `junie` |
| `.kiro/skills/` | `kiro-cli` |
| `.kode/skills/` | `kode` |
| `.lingma/skills/` | `lingma` |
| `.mcpjam/skills/` | `mcpjam` |
| `.minimax/skills/` | `minimax-code` |
| `.moxby/skills/` | `moxby` |
| `.mux/skills/` | `mux` |
| `.neovate/skills/` | `neovate` |
| `.ona/skills/` | `ona` |
| `.openclaw/skills/` | `openclaw` |
| `.openhands/skills/` | `openhands` |
| `.pi/agent/skills/` | `pi` |
| `.pochi/skills/` | `pochi` |
| `.posit/assistant/skills/` | `posit-assistant` |
| `.qoder-cn/skills/` | `qoder-cn` |
| `.qoder/skills/` | `qoder` |
| `.qwen/skills/` | `qwen-code` |
| `.reasonix/skills/` | `reasonix` |
| `.roo/skills/` | `roo` |
| `.rovodev/skills/` | `rovodev` |
| `.snowflake/cortex/skills/` | `cortex` |
| `.tabnine/agent/skills/` | `tabnine-cli` |
| `.terramind/skills/` | `terramind` |
| `.tinycloud/skills/` | `tinycloud` |
| `.trae-cn/skills/` | `trae-cn` |
| `.trae/skills/` | `trae` |
| `.vibe/skills/` | `mistral-vibe` |
| `.zcode/skills/` | `zcode` |

What this proves: the skill installs for each agent and its own self-tests
(`scripts/test_check_plan.py` and `scripts/test_interface_matrix.py`, with and without `python3
-O`) pass from the installed copy. What it does not prove: how any given agent behaves at run time
when it loads the skill — that is each agent's own runtime, which CI does not exercise.

The skill itself is harness-neutral and names no harness-specific tooling.

## The vendored pass-3 script

`scripts/interface_matrix.py` is a vendored copy of the script in the
[`interface-matrix`](https://github.com/macblackstuff/interface-matrix) skill, so this
skill never depends on a second skill being installed.
[`scripts/interface_matrix.UPSTREAM`](skills/system-adoption-pipeline/scripts/interface_matrix.UPSTREAM)
records the upstream repo, the path within it, and the sha256 of the copy shipped here. CI
fails if the copy no longer matches the pin, so re-syncing is deliberate: copy the upstream
file in and update the pin's `sha256` in the same commit.

## Contributing, security, license

[`CONTRIBUTING.md`](CONTRIBUTING.md) · [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) ·
[`SECURITY.md`](SECURITY.md) · [`CHANGELOG.md`](CHANGELOG.md) ·
MIT — see [`LICENSE`](LICENSE). Copyright (c) 2026 macblackstuff.
