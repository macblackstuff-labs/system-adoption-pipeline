#!/usr/bin/env bash
# Install this repo's skill with the Vercel `skills` CLI into a throwaway HOME, once per
# agent, and run the skill's own self-checks from each installed copy. With no arguments
# every agent the CLI supports is tested; the list is read from the CLI itself, so agents
# added by a future CLI release are covered without editing this script.
# Usage: .github/scripts/smoke-install.sh [agent...]
set -euo pipefail

repo=$(cd "$(dirname "$0")/../.." && pwd)

# Agents the CLI lists but cannot install globally. One line each, `agent reason`; every
# other listed agent must install and pass, so nothing is silently skipped.
exceptions="eve the CLI reports Eve does not support global skill installation
promptscript the CLI reports PromptScript does not support global skill installation"

# The CLI prints "Valid agents: a, b, c" when asked to install for an agent that does not
# exist, which is the only machine-readable list it offers. Colour codes are stripped and
# wrapped continuation lines are joined before the commas are split.
read_agents() {
  local home out
  home=$(mktemp -d)
  out=$(HOME="$home" XDG_CONFIG_HOME="$home/.config" XDG_DATA_HOME="$home/.local/share" npx --yes skills add "$repo" --skill system-adoption-pipeline \
          -g -a __invalid-agent__ -y --copy 2>&1 || true)
  rm -rf "$home"
  printf '%s\n' "$out" \
    | sed $'s/\033\\[[0-9;?]*[a-zA-Z]//g' \
    | awk '/Valid agents:/ {
             sub(/.*Valid agents:/, ""); buf = $0
             # A wrapped list continues on the next line; the break is always after a comma,
             # so anything following the last comma-terminated line is unrelated output.
             while (buf ~ /,[[:space:]]*$/ && (getline nxt) > 0) buf = buf nxt
             print buf; exit
           }' \
    | tr ',' '\n' \
    | sed 's/[^A-Za-z0-9_-]//g' \
    | grep -E '^[a-z0-9][a-z0-9_-]*$' || true
}

if [ $# -gt 0 ]; then
  agents=("$@")
else
  agents=()
  while IFS= read -r a; do agents+=("$a"); done < <(read_agents)
  [ "${#agents[@]}" -gt 0 ] || {
    echo "could not parse any agent name from the skills CLI's valid-agent list" >&2
    exit 1
  }
  echo "== skills CLI reports ${#agents[@]} agents"
fi

# Each agent gets its own throwaway home: most agents install into the shared
# ~/.agents/skills/, so a single home would make the one-installed-copy assert below pass
# for the first agent and then see the previous agent's copy for the rest. The install
# directory is derived from what landed, not hardcoded, so a future CLI release that moves
# an agent elsewhere is still tested rather than silently skipped.
tested=0
for agent in "${agents[@]}"; do
  reason=$(printf '%s\n' "$exceptions" | awk -v a="$agent" '$1 == a {$1=""; sub(/^ /, ""); print}')
  if [ -n "$reason" ]; then
    echo "== $agent: SKIPPED (documented exception) — $reason"
    continue
  fi
  home=$(mktemp -d)
  echo "== skills add -a $agent"
  # XDG vars too: agents that install under ~/.config honour XDG_CONFIG_HOME, which the
  # GitHub runner sets to the real home, so HOME alone would leak the install out of the
  # throwaway home.
  HOME="$home" XDG_CONFIG_HOME="$home/.config" XDG_DATA_HOME="$home/.local/share" \
    npx --yes skills add "$repo" --skill system-adoption-pipeline -g -a "$agent" -y --copy

  found=$(find "$home" -path "*/system-adoption-pipeline/SKILL.md" -print)
  count=$(printf '%s' "$found" | grep -c . || true)
  [ "$count" = 1 ] || { echo "expected 1 installed skill for $agent, found $count" >&2; exit 1; }
  dir=$(dirname "$found")
  echo "== $agent: installed at ${dir#"$home"/}"
  for f in SKILL.md references/RUNBOOK.md scripts/check_plan.py \
           scripts/test_check_plan.py scripts/interface_matrix.py \
           scripts/test_interface_matrix.py \
           scripts/interface_matrix.UPSTREAM \
           assets/templates/01-inventory.md assets/templates/02-completion.md \
           assets/templates/03-interfaces.md assets/templates/04-gap-register.md \
           assets/templates/05-work-packages.md assets/templates/06-ordering.md \
           assets/templates/07-verification.md; do
    [ -f "$dir/$f" ] || { echo "missing $f in installed skill for $agent" >&2; exit 1; }
  done
  # Both self-tests, with and without -O: the assertions the tests rely on are stripped
  # under -O, so the optimised run proves the skill still works where they are gone.
  for t in scripts/test_check_plan.py scripts/test_interface_matrix.py; do
    ( cd "$dir" && python3 "$t" )
    ( cd "$dir" && python3 -O "$t" )
  done
  ( cd "$dir/assets/templates" && python3 ../../scripts/check_plan.py \
      --inventory 01-inventory.md --interfaces 03-interfaces.md \
      --gaps 04-gap-register.md --packages 05-work-packages.md \
      --ordering 06-ordering.md )
  rm -rf "$home"
  tested=$((tested + 1))
done

echo "$tested of ${#agents[@]} agents installed and tested"
