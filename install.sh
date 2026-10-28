#!/usr/bin/env bash
# One-time setup for the gmail-drafts skill. Run it in your own Terminal
# (not inside a Claude sandbox), so it can reach Google:
#
#   ~/.claude/skills/gmail-drafts/install.sh [path/to/client.json]
#
# Safe to re-run: it updates the skill and skips the steps already done.
#   --skip-auth   stop before the Google sign-in (for testing)
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$SKILL_DIR/scripts/gmail_draft.py"
SKIP_AUTH=0
CLIENT_ARG=""
for arg in "$@"; do
  case "$arg" in
    --skip-auth) SKIP_AUTH=1 ;;
    *) CLIENT_ARG="$arg" ;;
  esac
done

bold() { printf '\n\033[1m%s\033[0m\n' "$1"; }
ok() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
die() { printf '  \033[31m✗\033[0m %s\n' "$1"; exit 1; }
ask() {
  local reply=""
  if [[ -t 0 ]] || ! { : </dev/tty; } 2>/dev/null; then
    read -r -p "  $1 " reply || true
  else
    read -r -p "  $1 " reply </dev/tty || true
  fi
  [[ "$reply" =~ ^[Yy] ]]
}
json_field() { sed -n "s/.*\"$1\": \"\{0,1\}\([^\",]*\)\"\{0,1\},\{0,1\}$/\1/p" | head -1; }

bold "1/5  Updating the skill"
if git -C "$SKILL_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git -C "$SKILL_DIR" pull --ff-only -q 2>/dev/null; then
    ok "Skill is up to date ($(git -C "$SKILL_DIR" log -1 --format=%h))"
  else
    warn "Could not pull updates (offline or local changes). Continuing with this version."
  fi
else
  ok "Installed without git (to update, run the same install line again)"
fi
[[ "$SKILL_DIR" == "$HOME/.claude/skills/gmail-drafts" ]] ||
  warn "The skill is in $SKILL_DIR. Claude Code only finds it in ~/.claude/skills/gmail-drafts."

bold "2/5  Checking uv and Google access"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  warn "uv (runs the Python script) is not installed."
  ask "Install it now from astral.sh? [y/N]" || die "uv is required. Install it from https://docs.astral.sh/uv/ and re-run."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  command -v uv >/dev/null 2>&1 || die "uv installation failed."
fi
ok "uv $(uv --version | cut -d' ' -f2)"
for host in oauth2.googleapis.com gmail.googleapis.com; do
  curl -s -o /dev/null --max-time 8 "https://$host" ||
    die "Cannot reach $host. Run this in your own Terminal, not in a Claude sandbox or cloud workspace."
done
ok "Google servers reachable"

STATUS="$(uv run -q --script "$SCRIPT" status 2>/dev/null || true)"
[[ -n "$STATUS" ]] || die "The skill script did not start. Check your internet connection and re-run."

bold "3/5  Installing the OAuth client file"
if [[ "$STATUS" == *'"client_installed": true'* && -z "$CLIENT_ARG" ]]; then
  ok "Already installed (project $(json_field project_id <<<"$STATUS"))"
else
  CLIENT="$CLIENT_ARG"
  if [[ -z "$CLIENT" ]]; then
    CLIENT="$(ls -t "$HOME"/Downloads/claude-gmail-drafts-client*.json "$HOME"/Downloads/client_secret_*.json 2>/dev/null | head -1 || true)"
    [[ -n "$CLIENT" ]] && ok "Found $(basename "$CLIENT") in Downloads"
  fi
  if [[ -z "$CLIENT" ]]; then
    warn "No client file found in Downloads (claude-gmail-drafts-client.json or client_secret_*.json)."
    read -r -p "  Drag the file into this window (or type its path), then press Return: " CLIENT </dev/tty
    CLIENT="${CLIENT//\\ / }"; CLIENT="${CLIENT%\'}"; CLIENT="${CLIENT#\'}"; CLIENT="${CLIENT%% }"
  fi
  uv run -q --script "$SCRIPT" install-client "$CLIENT" >/dev/null || die "That is not a valid Desktop OAuth client file."
  ok "Client file installed"
  [[ "$CLIENT" == "$HOME/Downloads/"* ]] && warn "You can delete $(basename "$CLIENT") from Downloads now."
  STATUS="$(uv run -q --script "$SCRIPT" status)"
fi

bold "4/5  Signing in to Google"
if [[ "$STATUS" == *'"signed_in": true'* ]]; then
  ok "Already signed in as $(json_field email <<<"$STATUS")"
elif [[ $SKIP_AUTH == 1 ]]; then
  warn "Skipped (--skip-auth)."
  exit 0
else
  echo "  A Google page opens in your browser. Pick your work account and click Allow."
  uv run -q --script "$SCRIPT" auth >/dev/null || die "Sign-in did not finish. Re-run this script to try again."
  STATUS="$(uv run -q --script "$SCRIPT" status)"
  ok "Signed in as $(json_field email <<<"$STATUS")"
fi
EMAIL="$(json_field email <<<"$STATUS")"

bold "5/5  Test draft"
if ask "Create a test draft to $EMAIL to check the links? [y/N]"; then
  TEST_JSON="$(mktemp)"
  printf '{"to": ["%s"], "subject": "gmail-drafts test (safe to delete)", "html_body": "<p>If this link opens the site directly, the setup works: <a href=\\"https://www.10xfounders.com\\">10x Founders website</a></p>"}' "$EMAIL" >"$TEST_JSON"
  RESULT="$(uv run -q --script "$SCRIPT" create "$TEST_JSON")"
  rm -f "$TEST_JSON"
  [[ "$RESULT" == *'"links_clean": true'* ]] || die "The draft's links were changed: $RESULT"
  ok "Test draft created with clean links. Find it in Gmail Drafts."
fi

bold "Done"
echo "  In Claude Code (Code tab of the Claude app, or 'claude' in Terminal), ask for an email draft."
echo "  The first time, Claude asks whether to use the Gmail API or Chrome; pick Gmail API."
