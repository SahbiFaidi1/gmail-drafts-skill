# gmail-drafts (Claude Code skill)

Create Gmail drafts from Claude with links that go straight to the site.

The hosted Gmail connector rewrites every link in a draft into a
`https://www.google.com/url?q=…` redirect, so recipients land on Google's
"Redirect Notice" page first. This skill skips the connector's draft tools and
offers two methods; the user picks one, and Claude can remember the choice:

- **Gmail API**: a bundled script (`scripts/gmail_draft.py`) uploads the email
  exactly as written. Fast, no browser needed. One-time setup: an OAuth client
  file from Google Cloud plus a single "Allow" sign-in, guided step by step by
  [references/api-setup.md](references/api-setup.md).
- **Chrome extension**: Claude writes the draft in Gmail through Claude in
  Chrome ([references/chrome-method.md](references/chrome-method.md)). No setup.

Both methods check the saved draft afterwards to confirm the links are clean.
Nothing is ever sent.

## Install

In your own Terminal (not inside a Claude sandbox or cloud workspace, which
can't reach Google), with the OAuth client file in your Downloads folder:

```bash
git clone https://github.com/SahbiFaidi1/gmail-drafts-skill.git ~/.claude/skills/gmail-drafts
~/.claude/skills/gmail-drafts/install.sh
```

`install.sh` updates the skill, installs [uv](https://docs.astral.sh/uv/) if
needed (asks first), checks that Google is reachable, installs the client file,
opens the one-time Google sign-in, and offers a test draft. It is safe to re-run
any time to get updates.

Then use Claude Code (the Code tab of the Claude app, or `claude` in Terminal)
and ask for an email draft. With no client file, Claude can still guide you
through creating one ([references/api-setup.md](references/api-setup.md)), or
use the Chrome method instead.

Credentials and settings are stored per user in `~/.config/gmail-drafts/`
and never in this repo.
