"""Version 2 dashboard: a local web page that shows, live, every email the watcher handles.

watch_gmail.py starts it automatically at http://localhost:8080 (only reachable from this computer).
"""
import json
import threading
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from openpyxl import load_workbook

from erasmus_inbox import tools

PORT = 8080
PAGE = Path(__file__).parent / "dashboard.html"
ACTIVITY_FILE = tools.BASE / "activity.json"  # keeps the history across restarts
STEPS = ["received", "reading", "filed", "excel", "reply", "done"]
_lock = threading.Lock()  # the web server runs in its own thread
_state = {"watcher": {"status": "starting", "detail": "", "last_check": None}, "emails": {}}

app = FastAPI()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _save() -> None:
    ACTIVITY_FILE.write_text(json.dumps(_state, indent=1, ensure_ascii=False), encoding="utf-8")


def set_watcher(status: str, detail: str = "") -> None:
    """Records what the watcher is doing: watching, paused or error."""
    with _lock:
        _state["watcher"].update(status=status, detail=detail, last_check=_now())


def email_received(msg_id: str, filename: str) -> None:
    """Adds a card for a new email (or resets it when a failed email is retried)."""
    info = tools.read_email(filename)
    with _lock:
        _state["emails"][msg_id] = {
            "id": msg_id, "received": _now(), "state": "processing", "from": info["from"],
            "subject": info["subject"], "attachments": [a["filename"] for a in info["attachments"]],
            "steps": {step: "pending" for step in STEPS} | {"received": "done"},
            "saved": [], "student": "", "reply": None, "summary": "", "error": "",
        }
        _save()


def agent_event(msg_id: str, event) -> None:
    """Moves the progress bar along as the agent calls its tools."""
    with _lock:
        card = _state["emails"][msg_id]
        for call in event.get_function_calls():
            card["steps"]["reading"] = "done"
            if call.name == "reply_to_student":
                card["reply"] = {"status": "writing", "text": (call.args or {}).get("answer", "")}
        for response in event.get_function_responses():
            result = response.response or {}
            if response.name == "save_attachment" and result.get("status") == "saved":
                card["saved"].append(result["path"].replace("\\", "/"))
                card["steps"]["filed"] = "done"
            elif response.name == "append_row" and result.get("status") in ("added", "updated"):
                card["student"] = result["student"]
                card["steps"]["excel"] = "done"
            elif response.name == "reply_to_student":
                card["reply"] = {**(card["reply"] or {}), **result}
                card["steps"]["reply"] = result.get("status", "done")  # "sent" or "drafted"
        _save()


def email_finished(msg_id: str, summary: str) -> None:
    """Marks the email done; steps it did not need (no PDF, no question) become "skipped"."""
    with _lock:
        card = _state["emails"][msg_id]
        card["steps"] = {step: "skipped" if status == "pending" else status for step, status in card["steps"].items()}
        card["steps"].update(reading="done", done="done")
        card.update(state="done", summary=summary)
        _save()


def email_failed(msg_id: str, error: Exception) -> None:
    """Shows in red where processing stopped; the watcher retries the email on its next round."""
    with _lock:
        card = _state["emails"].get(msg_id)
        if card:
            first_open = next((s for s in STEPS if card["steps"][s] == "pending"), "done")
            card["steps"][first_open] = "error"
            card.update(state="failed", error=str(error)[:300])
            _save()


def _students() -> list:
    """Returns students.xlsx as a list of rows (the first row is the header)."""
    if not tools.EXCEL.exists():
        return []
    try:
        workbook = load_workbook(tools.EXCEL)
        return [["" if v is None else str(v) for v in row] for row in workbook.active.iter_rows(values_only=True)]
    except Exception:  # e.g. the file is being saved right now; the next refresh will show it
        return []


@app.get("/")
def page() -> HTMLResponse:
    return HTMLResponse(PAGE.read_text(encoding="utf-8"))


@app.get("/api/state")
def state() -> dict:
    with _lock:
        snapshot = json.loads(json.dumps(_state))
    snapshot["emails"] = sorted(snapshot["emails"].values(), key=lambda e: e["received"], reverse=True)[:50]
    pdfs = sorted(tools.FILED.rglob("*.pdf")) if tools.FILED.exists() else []
    snapshot["files"] = [p.relative_to(tools.FILED).as_posix() for p in pdfs]
    snapshot["students"] = _students()
    return snapshot


@app.get("/files/{path:path}")
def pdf(path: str) -> FileResponse:
    """Opens a filed PDF; refuses anything outside the filed/ folder."""
    file = (tools.FILED / path).resolve()
    if tools.FILED.resolve() not in file.parents or file.suffix.lower() != ".pdf" or not file.is_file():
        raise HTTPException(404)
    return FileResponse(file)


@app.get("/students.xlsx")
def excel() -> FileResponse:
    if not tools.EXCEL.exists():
        raise HTTPException(404)
    return FileResponse(tools.EXCEL, filename="students.xlsx")


def start() -> None:
    """Loads earlier history and serves the dashboard in a background thread."""
    global _state
    if ACTIVITY_FILE.exists():
        _state = json.loads(ACTIVITY_FILE.read_text(encoding="utf-8"))
        for card in _state["emails"].values():
            if card["state"] == "processing":  # the watcher was stopped halfway; it will retry this email
                card.update(state="failed", error="Watcher stopped while processing; it will be retried.")
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
