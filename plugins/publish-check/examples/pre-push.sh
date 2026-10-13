#!/usr/bin/env bash
# publish-check as a git pre-push hook (example, not installed for you).
#   cp pre-push.sh /path/to/your/repo/.git/hooks/pre-push && chmod +x /path/to/your/repo/.git/hooks/pre-push
# PUBLISH_CHECK points at the script (default: where the manual install puts it).
# PUBLISH_CHECK_MAX_COMMITS limits how much history is scanned on each push (default 200).
set -euo pipefail

SCRIPT="${PUBLISH_CHECK:-$HOME/.claude/skills/publish-check/scripts/publish_check.py}"
ROOT="$(git rev-parse --show-toplevel)"

if ! python3 -I "$SCRIPT" "$ROOT" --max-commits "${PUBLISH_CHECK_MAX_COMMITS:-200}"; then
  echo "pre-push: publish-check found leaks (or could not run); push blocked. Review the report above." >&2
  exit 1
fi
