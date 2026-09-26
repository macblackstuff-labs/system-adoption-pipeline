# system-adoption-pipeline

An [Agent Skill](https://agentskills.io/specification) that turns a narrative description of
a large system — a transcript, a talk, a book chapter, a competitor teardown — into an
ordered, gap-closed build plan, through seven passes: extract → complete → interface matrix
→ gap register → work packages → ordering → deterministic verification.

The skill lives in [`skills/system-adoption-pipeline`](skills/system-adoption-pipeline):

| Path | What it is |
|---|---|
| [`SKILL.md`](skills/system-adoption-pipeline/SKILL.md) | The seven passes an agent follows, with each pass's input, output artifact and done-check. |
| [`assets/templates/`](skills/system-adoption-pipeline/assets/templates) | The seven artifact templates, copied into a working folder and filled in. |
| [`scripts/check_plan.py`](skills/system-adoption-pipeline/scripts/check_plan.py) | Pass 7: the deterministic checklist over the filled-in pass 1–6 artifacts. |
| [`scripts/interface_matrix.py`](skills/system-adoption-pipeline/scripts/interface_matrix.py) | Pass 3: builds an N² interface matrix and reports missing components, interface gaps, unconsumed outputs, feedback loops and never-stated pairs. |
| [`references/RUNBOOK.md`](skills/system-adoption-pipeline/references/RUNBOOK.md) | Operating the two scripts: health checks, procedures, incident playbooks. |

If you have only a goal rather than a written source, the SKILL.md's "Starting from a goal"
section says to interview the goal owner and write the answers up as a numbered spec first;
that spec becomes the pass-1 source.

## Install

With the [`skills` CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add macblackstuff-labs/system-adoption-pipeline
```

Or for one agent, without prompts:

```bash
npx skills add macblackstuff-labs/system-adoption-pipeline -a claude-code -y
```

Copying the [`skills/system-adoption-pipeline`](skills/system-adoption-pipeline) folder into
wherever your agent reads skills from works too: every path inside the skill is relative to
its own folder, so the destination does not matter. Verify a copy with its self-check, run
from inside the installed skill folder:

```bash
python3 scripts/test_check_plan.py    # expected: final line OK, exit 0
```

## Requirements

Python 3.9 or newer. Standard library only — no dependencies, no virtualenv, no install step.

On Windows the interpreter is usually `py` rather than `python3`: read every `python3` below and
in the skill's own docs as `py` there.

## Harnesses tested

CI installs the skill with the `skills` CLI on every push and pull request, once per agent in its
own throwaway home, and runs the skill's own checks from each installed copy. Six agents are
covered: `claude-code`, `codex`, `cursor`, `gemini-cli`, `github-copilot` and `opencode`. Five of
the six share one user-level skills directory (the `skills` CLI decides the target; see its
documentation for each agent's path), so on a real machine a single installed copy can serve all
five. CI still installs and tests each agent separately, so a change to any one agent's target is
caught.

The skill itself is harness-neutral and names no harness-specific tooling.

## The vendored pass-3 script

`scripts/interface_matrix.py` is a vendored copy of the script in the
[`interface-matrix`](https://github.com/macblackstuff-labs/interface-matrix) skill, so this
skill never depends on a second skill being installed.
[`scripts/interface_matrix.UPSTREAM`](skills/system-adoption-pipeline/scripts/interface_matrix.UPSTREAM)
records the upstream repo, the path within it, and the sha256 of the copy shipped here. CI
fails if the copy no longer matches the pin, so re-syncing is deliberate: copy the upstream
file in and update the pin's `sha256` in the same commit.

## License

MIT — see [`LICENSE`](LICENSE). Copyright (c) 2026 macblackstuff-labs.
