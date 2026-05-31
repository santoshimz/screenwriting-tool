#!/usr/bin/env bash
# Commit tracked changes and push to origin as santoshimz.
#
# Usage:
#   ./scripts/push.sh "Your commit message"
#   ./scripts/push.sh --push-only          # push existing commits, no new commit
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AUTHOR="santoshimz <santoshimz@gmail.com>"
REMOTE="${PUSH_REMOTE:-origin}"
BRANCH="$(git branch --show-current)"

if [[ "${1:-}" == "--push-only" ]]; then
  git push "$REMOTE" HEAD
  git status
  exit 0
fi

MSG="${1:-}"
if [[ -z "$MSG" ]]; then
  echo "Usage: ./scripts/push.sh \"commit message\"" >&2
  echo "       ./scripts/push.sh --push-only" >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  git add -A
  git commit --author="$AUTHOR" -m "$MSG"
else
  echo "Nothing to commit."
fi

if git rev-parse --abbrev-ref "@{u}" >/dev/null 2>&1; then
  git push "$REMOTE" "$BRANCH"
else
  git push -u "$REMOTE" HEAD
fi

git status
