# Contributing to system-adoption-pipeline

Bug reports, fixes and documentation improvements are welcome.

## Before you start

- Search [existing issues](https://github.com/macblackstuff-labs/system-adoption-pipeline/issues) first.
- For anything larger than a small fix, open an issue describing the change before writing code.
- Security problems go through [private vulnerability reporting](SECURITY.md), never a public issue.

## Development setup

The skill needs Python 3.9 or newer and nothing else: standard library only, no install step.

```bash
git clone https://github.com/macblackstuff-labs/system-adoption-pipeline.git
cd system-adoption-pipeline/skills/system-adoption-pipeline
python3 scripts/test_check_plan.py
python3 -O scripts/test_check_plan.py
python3 scripts/test_interface_matrix.py
python3 -O scripts/test_interface_matrix.py
```

Every run must pass, with and without `-O`.

## What CI checks

Every pull request runs these checks, and all of them must pass before merge:

| Check | What it enforces |
|---|---|
| `tests (3.9)`, `tests (3.x)` | the self-tests above on the oldest supported and the newest Python, and standard-library-only imports |
| `pin` | the vendored pass-3 files match their sha256 pins in `scripts/interface_matrix.UPSTREAM` |
| `validate` | `SKILL.md` passes [`skills-ref validate`](https://github.com/agentskills/agentskills) |
| `smoke` | the [`skills` CLI](https://github.com/vercel-labs/skills) installs the skill for six agents |
| `emails` | every commit uses a GitHub noreply address |

## Commit email

The email check rejects any commit whose author or committer address is not a GitHub noreply
address (`<id>+<username>@users.noreply.github.com`). Find yours at
[github.com/settings/emails](https://github.com/settings/emails), then set it for this clone:

```bash
git config user.email "<id>+<username>@users.noreply.github.com"
```

## Pull requests

- One change per pull request, with a test that fails without it (documentation-only changes excepted).
- Add a line to `CHANGELOG.md` under an `Unreleased` heading.
- Update `SKILL.md` or `references/` when behaviour the agent sees changes.
- Pull requests are squash-merged and the title becomes the commit subject, so write it as one.

## Vendored files

`scripts/interface_matrix.py` and `scripts/test_interface_matrix.py` are copies of a tagged release
of [interface-matrix](https://github.com/macblackstuff-labs/interface-matrix), pinned by sha256 in
`scripts/interface_matrix.UPSTREAM`. Do not edit them here: the `pin` check fails. Fix the matrix
upstream first, then re-vendor its new release in a pull request that updates the pins.

## License

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).
