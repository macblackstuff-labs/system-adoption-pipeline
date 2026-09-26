#!/usr/bin/env bash
# Install this repo's skill with the Vercel `skills` CLI into a throwaway HOME, once per
# agent named on the command line, and run the skill's own self-check from each installed
# copy. Usage: .github/scripts/smoke-install.sh claude-code codex cursor gemini-cli ...
set -euo pipefail

repo=$(cd "$(dirname "$0")/../.." && pwd)
[ $# -gt 0 ] || { echo "usage: $0 <agent> [agent...]" >&2; exit 2; }

# Each agent gets its own throwaway home: all agents except claude-code install into the
# shared ~/.agents/skills/, so a single home would make the one-installed-copy assert below
# pass for the first agent and then see the previous agent's copy for the rest. The install
# directory is derived from what landed, not hardcoded, so a future CLI release that moves
# an agent elsewhere is still tested rather than silently skipped.
for agent in "$@"; do
  home=$(mktemp -d)
  echo "== skills add --list ($agent)"
  HOME="$home" npx --yes skills add "$repo" --list
  echo "== skills add -a $agent"
  HOME="$home" npx --yes skills add "$repo" --skill system-adoption-pipeline -g -a "$agent" -y --copy

  found=$(find "$home" -path "*/system-adoption-pipeline/SKILL.md" -print)
  count=$(printf '%s' "$found" | grep -c . || true)
  [ "$count" = 1 ] || { echo "expected 1 installed skill for $agent, found $count" >&2; exit 1; }
  dir=$(dirname "$found")
  echo "== $agent: installed at ${dir#"$home"/}"
  for f in SKILL.md references/RUNBOOK.md scripts/check_plan.py \
           scripts/test_check_plan.py scripts/interface_matrix.py \
           scripts/interface_matrix.UPSTREAM \
           assets/templates/01-inventory.md assets/templates/02-completion.md \
           assets/templates/03-interfaces.md assets/templates/04-gap-register.md \
           assets/templates/05-work-packages.md assets/templates/06-ordering.md \
           assets/templates/07-verification.md; do
    [ -f "$dir/$f" ] || { echo "missing $f in installed skill for $agent" >&2; exit 1; }
  done
  ( cd "$dir" && python3 scripts/test_check_plan.py )
  ( cd "$dir/assets/templates" && python3 ../../scripts/check_plan.py \
      --inventory 01-inventory.md --interfaces 03-interfaces.md \
      --gaps 04-gap-register.md --packages 05-work-packages.md \
      --ordering 06-ordering.md )
  rm -rf "$home"
done
