# Chrome method: write the draft in Gmail via Claude in Chrome

No setup is needed beyond Claude in Chrome being connected and the user signed
in to Gmail in that Chrome. Load the Chrome tools in one ToolSearch call:
`tabs_context_mcp, tabs_create_mcp, navigate, computer, javascript_tool,
browser_batch, tabs_close_mcp`.

Unwrap any `https://www.google.com/url?q=<real>&…` link in the body to `<real>`
before you start.

## New email

1. Open a full-page compose window in a new tab. URL-encode every value:
   ```
   https://mail.google.com/mail/u/0/?view=cm&fs=1&to=<to>&cc=<cc>&bcc=<bcc>&su=<subject>
   ```
   Separate multiple recipients with commas. If the user has several Google
   accounts, use `authuser=<their email>` in place of `u/0`.
2. Wait about 4 seconds, then put the HTML body in with a synthetic paste.
   Gmail blocks `innerHTML` and `execCommand('insertHTML')` (Trusted Types),
   but accepts a paste event:
   ```js
   const b = document.querySelector('div[contenteditable="true"][aria-label*="Body" i], div[contenteditable="true"][role="textbox"]');
   b.focus();
   const dt = new DataTransfer();
   dt.setData('text/html', HTML_BODY);
   dt.setData('text/plain', PLAIN_TEXT_BODY);
   b.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
   [...b.querySelectorAll('a')].map(a => a.getAttribute('href'))
   ```
   The returned list should match the intended links. Gmail adds the user's
   signature by itself; the paste goes above it.
3. Wait about 3 seconds and take a screenshot to confirm "Draft saved" shows.
   **Never click Send.** Close the tab with `tabs_close_mcp`; the draft stays
   in Drafts.

## Reply in a thread

1. Open the thread: `https://mail.google.com/mail/u/0/#all/<threadId>` (thread id
   from the connector's `search_threads` / `get_thread`).
2. Take a screenshot, click **Reply** (or **Reply all** if the user asked), and
   wait for the reply box.
3. Paste the body with the same snippet as step 2 above, confirm "Draft saved",
   and close the tab.

## Update an existing draft

Open `https://mail.google.com/mail/u/0/#drafts`, open the draft, select the body
text you need to replace (or click into the right spot), and paste the new HTML
with the snippet. For a full rewrite, select the whole body first with
`cmd+a` inside the body field.

## Verify

Find the draft with the connector's `list_drafts` (query `subject:"…"`) and read
it with `get_draft`. The `href`s in `htmlBody` must be the real addresses, not
`google.com/url`. Reading through the connector doesn't change anything; only
writing does.
