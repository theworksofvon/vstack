#!/usr/bin/env bash
# Symlink every skill in this repo into each harness's skill directory.
# Safe to re-run: it only ever replaces links that point here.
set -euo pipefail

VSTACK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS="$VSTACK/skills"

# Add a harness by adding its user-level skills directory here.
TARGETS=(
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$HOME/.config/opencode/skills"
  "$HOME/.cursor/skills"
)

status=0
for skill in "$SKILLS"/*/; do
  name="$(basename "$skill")"
  for target in "${TARGETS[@]}"; do
    mkdir -p "$target"
    link="$target/$name"
    if [ -e "$link" ] && [ ! -L "$link" ]; then
      echo "SKIP  $link exists and is not a symlink" >&2
      status=1
      continue
    fi
    ln -sfn "${skill%/}" "$link"
  done
done

for target in "${TARGETS[@]}"; do
  n=$(find "$target" -maxdepth 1 -type l -lname "$SKILLS/*" | wc -l | tr -d ' ')
  printf "%-40s %s skills\n" "$target" "$n"
done
exit $status
