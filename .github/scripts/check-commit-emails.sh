#!/usr/bin/env bash
# Fail if any commit in the given range has an author or committer email that is not a GitHub
# noreply address. Keeps a contributor's real address out of this repository's history.
# Usage: .github/scripts/check-commit-emails.sh <base-sha> <head-sha>
#        .github/scripts/check-commit-emails.sh <head-sha>          # that one commit only
set -euo pipefail

zero=0000000000000000000000000000000000000000
case $# in
  1) range="-1 $1" ;;
  2) if [ "$1" = "$zero" ]; then
       range="-1 $2"
     elif ! git cat-file -e "$1^{commit}" 2>/dev/null; then
       # A forced push can name a base commit this checkout does not have; say so instead of
       # letting git rev-list die with a bare fatal.
       echo "base commit $1 is not in this checkout: fetch it (git fetch --unshallow, or a" >&2
       echo "full-history checkout) and run again" >&2
       exit 2
     else
       range="$1..$2"
     fi ;;
  *) echo "usage: $0 [<base-sha>] <head-sha>" >&2; exit 2 ;;
esac
# shellcheck disable=SC2086
commits=$(git rev-list $range)

# Every GitHub noreply form: <id>+<login>@users.noreply.github.com, <login>@users.noreply.github.com
# (a login may be a bot, e.g. dependabot[bot]), and noreply@github.com for the web/merge committer.
# Anchored regex, not a glob: a glob suffix match also accepts an address with whitespace in
# it, e.g. "evil@evil.com ok@users.noreply.github.com".
noreply='^(([0-9]+\+)?[A-Za-z0-9-]+(\[bot\])?@users\.noreply\.github\.com|noreply@github\.com)$'

bad=0
for c in $commits; do
  while IFS= read -r email; do
    if ! printf '%s\n' "$email" | grep -qE "$noreply"; then
      echo "$c: non-noreply email: $email" >&2; bad=1
    fi
  done < <(git show -s --format='%ae%n%ce' "$c")
done

if [ "$bad" = 1 ]; then
  echo "Set a noreply address for this repository and rewrite the commits:" >&2
  echo "  git config user.email '<id>+<user>@users.noreply.github.com'" >&2
  exit 1
fi
echo "all commit author and committer emails are GitHub noreply addresses"
