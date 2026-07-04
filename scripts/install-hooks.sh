#!/usr/bin/env bash
# Installs this skill's versioned git hooks (.githooks/) into .git/hooks/,
# which git never version-controls directly. Best-effort convenience
# only — see kicad-spice-coverage.md's "never trust the client" note:
# the GitHub Action is the actual authority for the SPICE coverage
# check, never this hook. Re-run this script after pulling an update to
# .githooks/ — it copies, it does not keep a live link.

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
hooks_source_dir="$repo_root/.githooks"
hooks_target_dir="$repo_root/.git/hooks"

if [ ! -d "$hooks_source_dir" ]; then
  echo "No .githooks/ directory found at $hooks_source_dir — nothing to install." >&2
  exit 1
fi

mkdir -p "$hooks_target_dir"

for hook_path in "$hooks_source_dir"/*; do
  [ -f "$hook_path" ] || continue
  hook_name="$(basename "$hook_path")"
  cp "$hook_path" "$hooks_target_dir/$hook_name"
  chmod +x "$hooks_target_dir/$hook_name"
  echo "Installed $hook_name -> .git/hooks/$hook_name"
done
