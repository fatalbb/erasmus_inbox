"""Connects to Gmail with OAuth2: finds new emails under a label, downloads them, writes draft replies."""
import base64
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

BASE = Path(__file__).parent
INBOX = BASE / "inbox"
CREDENTIALS = BASE / "credentials.json"  # OAuth client downloaded from Google Cloud
TOKEN = BASE / "token.json"  # saved after you click "Allow" the first time
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]  # read, label and draft; cannot delete for good
WATCH_LABEL = "Erasmus"
DONE_LABEL = "Erasmus/Processed"
_service = None
_label_ids = {}


def get_service():
    """Signs in to Gmail (opens the browser only the first time) and returns the API client."""
    global _service
    if _service is None:
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES) if TOKEN.exists() else None
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN.write_text(creds.to_json())
        _service = build("gmail", "v1", credentials=creds)
    return _service


def _label_id(name: str) -> str:
    """Returns the id of a Gmail label, creating the label if it does not exist yet."""
    if name not in _label_ids:
        labels = get_service().users().labels().list(userId="me").execute().get("labels", [])
        found = next((label["id"] for label in labels if label["name"] == name), None)
        if found is None:
            found = get_service().users().labels().create(userId="me", body={"name": name}).execute()["id"]
        _label_ids[name] = found
    return _label_ids[name]


def _ids(label_ids: list) -> set:
    """Returns the ids of the newest messages that have all the given labels."""
    resp = get_service().users().messages().list(userId="me", labelIds=label_ids, maxResults=100).execute()
    return {m["id"] for m in resp.get("messages", [])}


def find_new_messages() -> list:
    """Returns ids of emails labelled Erasmus that are not labelled Erasmus/Processed yet."""
    watch, done = _label_id(WATCH_LABEL), _label_id(DONE_LABEL)
    return sorted(_ids([watch]) - _ids([watch, done]))


def download_eml(msg_id: str) -> str:
    """Saves one Gmail message into inbox/ as gmail_<id>.eml and returns the file name."""
    raw = get_service().users().messages().get(userId="me", id=msg_id, format="raw").execute()["raw"]
    INBOX.mkdir(exist_ok=True)
    filename = f"gmail_{msg_id}.eml"
    (INBOX / filename).write_bytes(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    return filename


def mark_processed(msg_id: str) -> None:
    """Adds the Erasmus/Processed label so the email is never handled twice."""
    body = {"addLabelIds": [_label_id(DONE_LABEL)]}
    get_service().users().messages().modify(userId="me", id=msg_id, body=body).execute()


def create_draft_reply(msg_id: str, original, answer: str) -> str:
    """Puts a reply to the original email in Gmail Drafts (it is never sent) and returns the draft id."""
    reply = EmailMessage()
    reply["To"] = original["Reply-To"] or original["From"]
    subject = original["Subject"] or ""
    reply["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if original["Message-ID"]:
        reply["In-Reply-To"] = reply["References"] = original["Message-ID"]
    reply.set_content(answer)
    thread_id = get_service().users().messages().get(userId="me", id=msg_id, format="minimal").execute()["threadId"]
    body = {"message": {"raw": base64.urlsafe_b64encode(bytes(reply)).decode(), "threadId": thread_id}}
    return get_service().users().drafts().create(userId="me", body=body).execute()["id"]
