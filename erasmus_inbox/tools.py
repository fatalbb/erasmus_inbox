"""Tool functions the agent can call."""
import email
import re
import threading
from email import policy
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook, load_workbook
from pypdf import PdfReader

BASE = Path(__file__).parent  # the erasmus_inbox/ folder
INBOX = BASE / "inbox"
FILED = BASE / "filed"
EXCEL = BASE / "students.xlsx"
DRAFTS = BASE / "drafts"  # reply drafts for local test emails (Gmail emails get real Gmail drafts)
DOC_TYPES = {"LearningAgreement", "Transcript", "Insurance", "CertificateOfArrival"}
HEADERS = ["Name", "Host university", "Start date", "End date", "Documents received"]
_excel_lock = threading.Lock()  # stops two tool calls writing the Excel file at once


def _load(filename: str):
    """Opens one .eml file from the inbox folder."""
    path = INBOX / Path(filename).name  # .name blocks tricks like ../../secret.txt
    with open(path, "rb") as f:
        return email.message_from_binary_file(f, policy=policy.default)


def _clean(text: str) -> str:
    """Keeps only letters, digits, - and _ so names are safe in file paths."""
    return re.sub(r"[^\w-]", "", text.strip().replace(" ", "-"))


def list_emails() -> dict:
    """Lists the .eml files waiting in the inbox folder."""
    return {"emails": sorted(p.name for p in INBOX.glob("*.eml"))}


def read_email(filename: str) -> dict:
    """Returns sender, subject, body and the text inside each PDF attachment.

    Args:
        filename: name of the .eml file, as returned by list_emails.
    """
    msg = _load(filename)
    body = msg.get_body(preferencelist=("plain",))
    attachments = []
    for part in msg.iter_attachments():
        text = ""
        if part.get_content_type() == "application/pdf":
            pages = PdfReader(BytesIO(part.get_content())).pages
            text = "\n".join(page.extract_text() or "" for page in pages)
        attachments.append({"filename": part.get_filename(), "text": text[:2000]})
    return {
        "from": msg["From"],
        "subject": msg["Subject"],
        "body": body.get_content() if body else "",
        "attachments": attachments,
    }


def save_attachment(email_filename: str, attachment_filename: str, surname: str,
                    name: str, doc_type: str, academic_year: str) -> dict:
    """Saves one attachment as filed/<Surname_Name>/<Surname>_<Name>_<DocType>_<YYYY-YY>.pdf.

    Args:
        email_filename: the .eml file the attachment is in.
        attachment_filename: the attachment's original file name.
        surname: student's family name, e.g. "Fischer".
        name: student's first name, e.g. "Lena".
        doc_type: one of LearningAgreement, Transcript, Insurance, CertificateOfArrival.
        academic_year: written as YYYY-YY, e.g. "2026-27".
    """
    if doc_type not in DOC_TYPES:
        return {"status": "error", "message": f"doc_type must be one of {sorted(DOC_TYPES)}"}
    if not re.fullmatch(r"\d{4}-\d{2}", academic_year):
        return {"status": "error", "message": "academic_year must look like 2026-27"}
    for part in _load(email_filename).iter_attachments():
        if part.get_filename() == attachment_filename:
            surname, name = _clean(surname), _clean(name)
            folder = FILED / f"{surname}_{name}"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{surname}_{name}_{doc_type}_{academic_year}.pdf"
            path.write_bytes(part.get_content())
            return {"status": "saved", "path": str(path.relative_to(BASE))}
    return {"status": "error", "message": f"No attachment called {attachment_filename}"}


def append_row(surname: str, name: str, host_university: str, start_date: str,
               end_date: str, documents_received: str) -> dict:
    """Adds the student's row to students.xlsx, or updates it if the student is already there.

    Args:
        surname: student's family name.
        name: student's first name.
        host_university: host university, or "" if unknown.
        start_date: mobility start date as YYYY-MM-DD, or "" if unknown.
        end_date: mobility end date as YYYY-MM-DD, or "" if unknown.
        documents_received: comma-separated doc types, e.g. "LearningAgreement, Insurance".
    """
    full_name = f"{surname.strip()} {name.strip()}"
    new_docs = {d.strip() for d in documents_received.split(",") if d.strip()}
    with _excel_lock:
        if EXCEL.exists():
            wb = load_workbook(EXCEL)
            ws = wb.active
        else:
            wb = Workbook()
            ws = wb.active
            ws.append(HEADERS)
        for row in ws.iter_rows(min_row=2):
            if str(row[0].value).lower() == full_name.lower():
                for cell, value in zip(row[1:4], [host_university, start_date, end_date]):
                    if value:
                        cell.value = value
                old_docs = {d.strip() for d in str(row[4].value or "").split(",") if d.strip()}
                row[4].value = ", ".join(sorted(old_docs | new_docs))
                action = "updated"
                break
        else:
            ws.append([full_name, host_university, start_date, end_date, ", ".join(sorted(new_docs))])
            action = "added"
        try:
            wb.save(EXCEL)
        except PermissionError:
            return {"status": "error", "message": "students.xlsx is open in Excel. Close it and try again."}
    return {"status": action, "student": full_name}


def reply_to_student(email_filename: str, answer: str) -> dict:
    """Replies to whoever sent the email. Gmail replies are sent automatically when that is safe,
    otherwise they are saved in Gmail Drafts for staff to check.

    Args:
        email_filename: the .eml file the question came from.
        answer: the full reply text, from greeting to sign-off.
    """
    filename = Path(email_filename).name
    if filename.startswith("gmail_"):
        from . import gmail_client  # imported here so version 1 works without Gmail set up

        msg_id = Path(filename).stem.removeprefix("gmail_")
        original = _load(filename)
        blocker = gmail_client.auto_send_blocker(msg_id, original)
        if not blocker:
            gmail_client.send_reply(msg_id, original, answer)
            return {"status": "sent", "to": original["Reply-To"] or original["From"]}
        gmail_client.create_draft_reply(msg_id, original, answer)
        return {"status": "drafted", "where": "Gmail Drafts", "reason": blocker}
    DRAFTS.mkdir(exist_ok=True)
    path = DRAFTS / f"{Path(filename).stem}_reply.txt"
    path.write_text(answer, encoding="utf-8")
    return {"status": "drafted", "where": str(path.relative_to(BASE))}