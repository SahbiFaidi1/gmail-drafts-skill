#!/usr/bin/env bash
# Build a single setup file for teammates without GitHub access.
# It packs this skill plus the OAuth client file into one script; the teammate
# saves it and runs `bash ~/Downloads/gmail-drafts-setup.sh` in Terminal.
#
#   tools/build-setup-bundle.sh <client.json> [output.sh]
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT="${1:?usage: build-setup-bundle.sh <client.json> [output.sh]}"
OUT="${2:-$SKILL_DIR/dist/gmail-drafts-setup.sh}"
grep -q '"installed"' "$CLIENT" || { echo "Not a Desktop OAuth client file: $CLIENT" >&2; exit 1; }
mkdir -p "$(dirname "$OUT")"

{
  cat <<'HEADER'
#!/usr/bin/env bash
# gmail-drafts setup: installs the Claude skill for Gmail drafts with clean links.
# Run it in Terminal:  bash ~/Downloads/gmail-drafts-setup.sh
set -euo pipefail
DEST="$HOME/.claude/skills/gmail-drafts"
TMP="$(mktemp -d)"
SELF="${BASH_SOURCE[0]}"

echo "Installing the gmail-drafts skill into $DEST"
sed -n '/^__SKILL__$/,/^__CLIENT__$/p' "$SELF" | sed '1d;$d' | base64 --decode | tar -xzf - -C "$TMP"
sed -n '/^__CLIENT__$/,$p' "$SELF" | sed '1d' | base64 --decode >"$TMP/claude-gmail-drafts-client.json"

if [[ -e "$DEST" ]]; then
  BACKUP="$HOME/.claude/gmail-drafts.backup-$(date +%Y%m%d-%H%M%S)"  # outside skills/, so Claude sees one copy
  mv "$DEST" "$BACKUP"
  echo "Moved the previous version to $BACKUP"
fi
mkdir -p "$(dirname "$DEST")"
mv "$TMP/gmail-drafts" "$DEST"
chmod +x "$DEST/install.sh"

status=0
"$DEST/install.sh" "$@" "$TMP/claude-gmail-drafts-client.json" || status=$?
rm -rf "$TMP"
[[ $status == 0 ]] && echo "  You can delete $(basename "$SELF") from Downloads now."
exit $status
HEADER
  echo "__SKILL__"
  COPYFILE_DISABLE=1 tar -czf - --exclude .git --exclude dist --exclude tools --exclude '__pycache__' \
    --exclude .DS_Store -C "$(dirname "$SKILL_DIR")" "$(basename "$SKILL_DIR")" | base64
  echo "__CLIENT__"
  base64 <"$CLIENT"
} >"$OUT"
chmod +x "$OUT"
echo "Built $OUT ($(wc -c <"$OUT" | tr -d ' ') bytes, skill version $(git -C "$SKILL_DIR" log -1 --format=%h 2>/dev/null || echo unknown))"
