# API method: one-time setup

Gmail does not accept a plain API key for reading or writing someone's mail.
What the user provides instead is an **OAuth client file** (a small JSON file
from Google Cloud), followed by a one-time Google sign-in where they click
"Allow". Explain it to the user in those words, not as an "API key".

Prerequisite: `uv` must be installed (`which uv`). If it is missing, ask before
installing it with `curl -LsSf https://astral.sh/uv/install.sh | sh`.

Run `status` after each step to confirm progress.

## Step 1. Get the OAuth client file

Ask which applies:

**A. Your organisation already has one.** At 10x Founders the internal client
lives in the Google Cloud project `claude-gmail-drafts-513009` (set up by
Sahbi Faidi). Because the app is *Internal*, any 10xfounders.com account can
use the same client file: ask its owner for it, then skip to step 2. To share
the file, the owner downloads it again from Google Auth Platform → Clients.

**B. Create a new one.** Offer two ways:

- **The user does it**, with you guiding them one step at a time:
  1. https://console.cloud.google.com → create a project, e.g. "Claude Gmail Drafts".
  2. APIs & Services → Library → **Gmail API** → **Enable**.
  3. Google Auth Platform → Get started: app name "Claude Gmail Drafts", their
     email as support contact, **Audience: Internal**, their email as contact,
     agree to the User Data Policy → Create.
     (Internal needs a Google Workspace account. A personal @gmail.com account
     must pick External and add itself under Audience → Test users. Sign-ins
     then expire every 7 days.)
  4. Google Auth Platform → Clients → Create client → **Desktop app** → Create →
     **Download JSON**.
- **You do it in their Chrome** (Claude in Chrome), only after the user says yes,
  since it creates a project and credentials in their Google account. Same steps
  as above. Stop and hand over to the user at:
  - Google's identity check (passkey or password): only the user can do it.
  - The "Google API Services: User Data Policy" checkbox: tick it only after
    the user explicitly agrees in chat.
  - Use the project ID Google shows on the create page in the later URLs, e.g.
    `https://console.cloud.google.com/apis/library/gmail.googleapis.com?project=<id>`.
  - After clicking Enable on the Gmail API, reload its page and confirm the
    status says Enabled. The first click sometimes doesn't take.

## Step 2. Install the client file

The download lands in `~/Downloads/client_secret_*.json` (find it with
`ls -t ~/Downloads/client_secret_*.json | head -1`), or the user tells you
where it is. Then:

```bash
uv run --script <skill-dir>/scripts/gmail_draft.py install-client "<path>"
```

It checks the file is a Desktop client and copies it to
`~/.config/gmail-drafts/credentials.json`. Tell the user they can then delete
the copy in Downloads.

## Step 3. Sign in once

Run `auth` **in the background**, because it waits until the user approves:

```bash
uv run --script <skill-dir>/scripts/gmail_draft.py auth
```

A Google page opens in the default browser. Tell the user to pick their account
and click **Allow**. Clicking Allow is their decision, so never click it for them.
If no page opens, read the command output for the `https://accounts.google.com/...`
URL and give it to them. The command finishes once they approve (5-minute
timeout); then `status` shows `signed_in: true` and their email.

## Step 4. Confirm

Ask whether to make a short test draft to themselves. If yes, run `create`
and check that `links_clean` is `true`. Then offer `set-method api` so future
drafts use the API without asking.

## Troubleshooting

- **"Access blocked: … admin hasn't approved this app"**: the Workspace admin
  has to trust the client ID (Admin console → Security → API controls → App
  access control).
- **"This app isn't verified"**: the audience is External. Use Internal on
  Workspace accounts.
- **`next_step: "auth"` on later runs**: the token was revoked or expired. Run
  step 3 again.
- Files live in `~/.config/gmail-drafts/` (`credentials.json`, `token.json`,
  `settings.json`), readable only by the user.
