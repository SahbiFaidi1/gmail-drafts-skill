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

```bash
git clone https://github.com/SahbiFaidi1/gmail-drafts-skill.git ~/.claude/skills/gmail-drafts
```

Requires [uv](https://docs.astral.sh/uv/) for the API method. Then ask Claude
to "draft an email"; on first use it asks which method to use and walks you
through the setup.

Credentials and settings are stored per user in `~/.config/gmail-drafts/`
and never in this repo.
