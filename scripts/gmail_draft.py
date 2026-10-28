# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-api-python-client>=2.100",
#     "google-auth-oauthlib>=1.2",
# ]
# ///
"""Create Gmail drafts through the Gmail API with links kept exactly as written.

The hosted Gmail connector rewrites every link into a google.com/url redirect.
This script builds the MIME message itself and uploads it unchanged.

Commands (run with `uv run --script gmail_draft.py <command>`):
    status                      setup state, saved method preference, signed-in address
    install-client <file.json>  store the OAuth client file downloaded from Google Cloud
    auth                        one-time Google sign-in (opens the browser)
    set-method api|chrome|ask   save the preferred drafting method
    create <draft.json>         create a draft ("-" reads JSON from stdin)
    update <draft_id> <draft.json>  replace a draft's full content
    check <draft_id>            list the links saved in a draft and whether they are clean
    send <draft_id>             send an existing draft (only after the user approved it in chat)

draft.json fields: to, cc, bcc (lists), subject, html_body, text_body,
include_signature (default true), reply_to_message_id, attachments (list of file paths).
Every command prints one JSON object.
"""

import base64
import email
import email.policy
import html
import json
import mimetypes
import re
import shutil
import sys
from email.message import EmailMessage
from email.utils import getaddresses
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CONFIG_DIR = Path.home() / ".config" / "gmail-drafts"
CLIENT_SECRET = CONFIG_DIR / "credentials.json"
TOKEN = CONFIG_DIR / "token.json"
SETTINGS = CONFIG_DIR / "settings.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",  # create and update drafts
    "https://www.googleapis.com/auth/gmail.readonly",  # read the message being replied to
    "https://www.googleapis.com/auth/gmail.settings.basic",  # read the Gmail signature
]

GOOGLE_REDIRECT = re.compile(r"https?://(?:www\.)?google\.[a-z.]+/url\?[^\s\"'<>]+")


def out(obj: dict) -> None:
    print(json.dumps(obj, indent=1))


def fail(msg: str, **extra) -> None:
    out({"ok": False, "error": msg, **extra})
    sys.exit(1)


# ---------- settings and auth ----------


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def gmail():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not CLIENT_SECRET.exists():
        fail("No OAuth client installed. Follow references/api-setup.md.", next_step="setup")
    if not TOKEN.exists():
        fail("Not signed in. Run the `auth` command.", next_step="auth")
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:  # revoked or expired refresh token
                fail(f"Google sign-in no longer valid ({e}). Run the `auth` command.", next_step="auth")
            TOKEN.write_text(creds.to_json())
        else:
            fail("Google sign-in expired. Run the `auth` command.", next_step="auth")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def cmd_status() -> None:
    state = {
        "ok": True,
        "method": load_settings().get("method", "ask"),
        "client_installed": CLIENT_SECRET.exists(),
        "signed_in": TOKEN.exists(),
        "email": None,
    }
    if state["client_installed"]:
        state["project_id"] = json.loads(CLIENT_SECRET.read_text()).get("installed", {}).get("project_id")
    if state["client_installed"] and state["signed_in"]:
        state["email"] = gmail().users().getProfile(userId="me").execute()["emailAddress"]
    out(state)


def cmd_install_client(path: str) -> None:
    src = Path(path).expanduser()
    try:
        data = json.loads(src.read_text())
    except (OSError, json.JSONDecodeError) as e:
        fail(f"Could not read {src}: {e}")
    if "installed" not in data:
        fail("This is not a Desktop app OAuth client file (no 'installed' section). "
             "Create the client with application type 'Desktop app'.")
    shutil.copyfile(src, CLIENT_SECRET)
    CLIENT_SECRET.chmod(0o600)
    out({"ok": True, "saved_to": str(CLIENT_SECRET), "project_id": data["installed"].get("project_id")})


def cmd_auth() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CLIENT_SECRET.exists():
        fail("No OAuth client installed. Follow references/api-setup.md.", next_step="setup")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", timeout_seconds=300)
    TOKEN.write_text(creds.to_json())
    TOKEN.chmod(0o600)
    out({"ok": True, "token_saved_to": str(TOKEN)})


def cmd_set_method(method: str) -> None:
    if method not in ("api", "chrome", "ask"):
        fail("Method must be api, chrome or ask.")
    SETTINGS.write_text(json.dumps({**load_settings(), "method": method}, indent=1))
    out({"ok": True, "method": method})


# ---------- message building ----------


def unwrap_google_redirects(text: str, is_html: bool) -> str:
    """Turn google.com/url?q=<real> links (e.g. copied from Google Docs) back into <real>."""

    def repl(m: re.Match) -> str:
        raw = html.unescape(m.group(0)) if is_html else m.group(0)
        target = parse_qs(urlparse(raw).query).get("q", [None])[0]
        if not target:
            return m.group(0)
        return html.escape(target, quote=True) if is_html else target

    return GOOGLE_REDIRECT.sub(repl, text)


def html_to_text(body: str) -> str:
    body = re.sub(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", body, flags=re.I | re.S)
    body = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", body, flags=re.I)
    body = re.sub(r"<[^>]+>", "", body)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(body)).strip()


def default_signature(svc) -> str:
    for alias in svc.users().settings().sendAs().list(userId="me").execute().get("sendAs", []):
        if alias.get("isDefault"):
            return alias.get("signature", "")
    return ""


def build_message(svc, d: dict) -> dict:
    to, cc, bcc = d.get("to") or [], d.get("cc") or [], d.get("bcc") or []
    subject = d.get("subject", "")
    html_body = unwrap_google_redirects(d.get("html_body", ""), is_html=True)
    text_body = unwrap_google_redirects(d.get("text_body", ""), is_html=False)

    if d.get("include_signature", True) and (sig := default_signature(svc)):
        if html_body:
            html_body = f'{html_body}<br><div class="gmail_signature">{sig}</div>'
        if text_body:
            text_body = f"{text_body}\n\n-- \n{html_to_text(sig)}"

    msg = EmailMessage()
    thread_id = None
    if reply_to := d.get("reply_to_message_id"):
        orig = (
            svc.users()
            .messages()
            .get(
                userId="me",
                id=reply_to,
                format="metadata",
                metadataHeaders=["Message-ID", "References", "Subject", "From", "Reply-To", "To"],
            )
            .execute()
        )
        thread_id = orig["threadId"]
        headers = {h["name"].lower(): h["value"] for h in orig["payload"]["headers"]}
        if mid := headers.get("message-id"):
            msg["In-Reply-To"] = mid
            msg["References"] = f"{headers.get('references', '')} {mid}".strip()
        if not subject:
            orig_subject = headers.get("subject", "")
            subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"
        if not to:
            me = svc.users().getProfile(userId="me").execute()["emailAddress"].lower()
            sender = [addr for _, addr in getaddresses([headers.get("reply-to") or headers.get("from", "")])]
            if all(addr.lower() == me for addr in sender):
                # Following up on our own message: reply to whoever we wrote to.
                sender = [addr for _, addr in getaddresses([headers.get("to", "")])]
            to = sender

    if to:
        msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = subject

    msg.set_content(text_body or html_to_text(html_body) or "")
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    for path in d.get("attachments") or []:
        file = Path(path).expanduser()
        if not file.is_file():
            fail(f"Attachment not found: {file}")
        ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(file.read_bytes(), maintype=maintype, subtype=subtype, filename=file.name)

    message = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
    if thread_id:
        message["threadId"] = thread_id
    return message


def check_links(svc, draft_id: str = "", message_id: str = "") -> dict:
    """Re-read the saved draft (or sent message) and report whether the links are untouched."""
    if message_id:
        raw = svc.users().messages().get(userId="me", id=message_id, format="raw").execute()["raw"]
    else:
        raw = svc.users().drafts().get(userId="me", id=draft_id, format="raw").execute()["message"]["raw"]
    parsed = email.message_from_bytes(base64.urlsafe_b64decode(raw), policy=email.policy.default)
    saved = "\n".join(
        part.get_content() for part in parsed.walk() if part.get_content_maintype() == "text"
    )
    return {
        "links_clean": GOOGLE_REDIRECT.search(saved) is None,
        "links": sorted(set(re.findall(r'href="([^"]+)"', saved))),
    }


def draft_result(svc, draft: dict) -> dict:
    message_id = draft["message"]["id"]
    return {
        "ok": True,
        "draft_id": draft["id"],
        "message_id": message_id,
        "thread_id": draft["message"].get("threadId"),
        "view_url": f"https://mail.google.com/mail/#drafts?compose={message_id}",
        **check_links(svc, draft["id"]),
    }


def read_draft_json(path: str) -> dict:
    try:
        return json.loads(sys.stdin.read() if path == "-" else Path(path).read_text())
    except (OSError, json.JSONDecodeError) as e:
        fail(f"Could not read draft JSON: {e}")


def cmd_create(path: str) -> None:
    svc = gmail()
    message = build_message(svc, read_draft_json(path))
    draft = svc.users().drafts().create(userId="me", body={"message": message}).execute()
    out(draft_result(svc, draft))


def cmd_update(draft_id: str, path: str) -> None:
    svc = gmail()
    message = build_message(svc, read_draft_json(path))
    draft = svc.users().drafts().update(userId="me", id=draft_id, body={"message": message}).execute()
    out(draft_result(svc, draft))


def cmd_check(draft_id: str) -> None:
    out({"ok": True, **check_links(gmail(), draft_id)})


def cmd_send(draft_id: str) -> None:
    svc = gmail()
    sent = svc.users().drafts().send(userId="me", body={"id": draft_id}).execute()
    out({"ok": True, "sent_message_id": sent["id"], "thread_id": sent.get("threadId"),
         **check_links(svc, message_id=sent["id"])})


COMMANDS = {
    "status": (cmd_status, 0),
    "install-client": (cmd_install_client, 1),
    "auth": (cmd_auth, 0),
    "set-method": (cmd_set_method, 1),
    "create": (cmd_create, 1),
    "update": (cmd_update, 2),
    "check": (cmd_check, 1),
    "send": (cmd_send, 1),
}

if __name__ == "__main__":
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    name, *args = sys.argv[1:] or ["status"]
    if name not in COMMANDS or len(args) != COMMANDS[name][1]:
        fail(f"Usage: {', '.join(COMMANDS)} — see the docstring at the top of this file.")
    try:
        COMMANDS[name][0](*args)
    except Exception as e:
        if type(e).__name__ != "HttpError":
            raise
        hint = {404: "Not found: the draft was probably sent or deleted. Create a new one instead.",
                400: "Gmail rejected the request (e.g. that draft was already sent)."}.get(e.resp.status, "")
        fail(f"Gmail API error {e.resp.status}: {e.reason}", hint=hint)
