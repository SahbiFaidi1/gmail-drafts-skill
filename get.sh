#!/usr/bin/env bash
# Download (or update) the gmail-drafts skill and run its setup, without git
# or a GitHub account. Run in your own Terminal:
#
#   curl -fsSL https://raw.githubusercontent.com/SahbiFaidi1/gmail-drafts-skill/main/get.sh | bash
#
# Arguments after `bash -s --` go to install.sh (e.g. a path to the client file).
set -euo pipefail

REPO="SahbiFaidi1/gmail-drafts-skill"
DEST="$HOME/.claude/skills/gmail-drafts"

if git -C "$DEST" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  # A git checkout updates itself in install.sh.
  exec bash "$DEST/install.sh" "$@"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "Downloading the gmail-drafts skill from github.com/$REPO"
curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/main" | tar -xzf - -C "$TMP"
SRC="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)"
[[ -f "$SRC/SKILL.md" ]] || { echo "Download failed: no SKILL.md in the archive." >&2; exit 1; }

if [[ -e "$DEST" ]]; then
  BACKUP="$HOME/.claude/gmail-drafts.backup-$(date +%Y%m%d-%H%M%S)"  # outside skills/, so Claude sees one copy
  mv "$DEST" "$BACKUP"
  echo "Moved the previous version to $BACKUP"
fi
mkdir -p "$(dirname "$DEST")"
mv "$SRC" "$DEST"
chmod +x "$DEST/install.sh" "$DEST/get.sh"

bash "$DEST/install.sh" "$@"
