# Erasmus Inbox Agent: Technical Documentation

For setup instructions, see [README.md](README.md). This document explains how the project works, how to extend it, and what its limits are.

## Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Components](#3-components)
4. [Data conventions](#4-data-conventions)
5. [Processing walkthrough](#5-processing-walkthrough)
6. [Answering student questions](#6-answering-student-questions)
7. [Safety and privacy design](#7-safety-and-privacy-design)
8. [Test data and expected results](#8-test-data-and-expected-results)
9. [Customising and extending](#9-customising-and-extending)
10. [Limitations](#10-limitations)
11. [Troubleshooting](#11-troubleshooting)
12. [Ideas for next steps](#12-ideas-for-next-steps)
13. [Version 2: live Gmail watcher](#13-version-2-live-gmail-watcher)
14. [Glossary](#14-glossary)

---

## 1. Overview

An Erasmus office receives many emails from students with documents attached under meaningless file names. Staff have to open each one, work out whose it is and what it is, rename it, file it, and note in a spreadsheet which documents each student has handed in.

This project hands that routine work to an **AI agent**. The agent uses a language model (Gemini) to *understand* the emails, and four small Python functions (**tools**) to *act*: list the emails, read one, save an attachment and update the spreadsheet. The model decides which tool to call and with which values; the tools do the actual file work and check what they're given.

| Concern | Who handles it |
|---|---|
| Understanding names, document types, dates in any format | Gemini (the model) |
| Reading `.eml` files and extracting PDF text | `read_email` tool |
| Validating and writing files | `save_attachment` tool |
| Keeping one Excel row per student | `append_row` tool |
| Answering questions | Gemini, limited to `faq.txt` |

## 2. Architecture

```
            ┌──────────────────────────────┐
  You  ───► │  ADK web UI  (localhost:8000) │
            └──────────────┬───────────────┘
                           │ your message
                           ▼
            ┌──────────────────────────────┐        ┌─────────────────────┐
            │  root_agent  (agent.py)      │ ◄────► │  Gemini API         │
            │  instructions + FAQ + tools  │        │  flash-lite-latest  │
            └──────────────┬───────────────┘        └─────────────────────┘
                           │ tool calls chosen by the model
                           ▼
            ┌──────────────────────────────┐
            │  tools.py                    │
            │  list_emails   read_email    │──► inbox/*.eml        (read only)
            │  save_attachment             │──► filed/<Surname_Name>/*.pdf
            │  append_row                  │──► students.xlsx
            └──────────────────────────────┘
```

**The agent loop.** ADK sends your message, the instructions and the descriptions of the tools to Gemini. Gemini replies either with text (the answer) or with one or more **function calls**, such as `read_email("email_03.eml")`. ADK runs those Python functions, sends their results back to Gemini, and repeats until Gemini replies with plain text. Every step appears as an event in the web UI's **Events** tab.

## 3. Components

### 3.1 `erasmus_inbox/agent.py`

Defines `root_agent`, the object ADK looks for when it loads the folder.

| Field | Value | Purpose |
|---|---|---|
| `name` | `erasmus_inbox` | Name shown in the ADK menu |
| `model` | `gemini-flash-lite-latest` | Small, fast Gemini model with its own free daily quota. Earlier choices were `gemini-flash-latest`, which was often overloaded (`503`), and then `gemini-3.5-flash`, which is more accurate but whose free tier allows only 20 requests a day (`429`). Switch back to it if you enable billing. |
| `generate_content_config` | `thinking_level="low"` | Less "thinking" before each answer, so replies are faster. The tasks are simple, so accuracy was unchanged in testing. |
| `description` | one sentence | Summary of what the agent does, used when agents are combined |
| `instruction` | `INSTRUCTION + FAQ` | The system prompt: the 5-step filing procedure, the FAQ rule and the contents of `faq.txt` |
| `tools` | the four functions | What the agent is allowed to do |

`faq.txt` is read once, when the agent loads, so restart `adk web` after you edit it.

### 3.2 `erasmus_inbox/tools.py`

All paths are built from `BASE`, the `erasmus_inbox/` folder, so the tools work whichever folder you start `adk web` from. ADK turns each function's **type hints and docstring** into a description that Gemini reads, which is why the docstrings are detailed.

Every tool returns a `dict`. When something goes wrong, it returns `{"status": "error", "message": ...}` instead of raising an exception, so the model can read the problem and try again.

#### `list_emails() -> dict`

Returns `{"emails": ["email_01.eml", ...]}`: the sorted names of every `.eml` file in `inbox/`.

#### `read_email(filename) -> dict`

| Parameter | Description |
|---|---|
| `filename` | Name of an `.eml` file, as returned by `list_emails` |

Returns:

```json
{
  "from": "lena.fischer@student.example.org",
  "subject": "insurance",
  "body": "Hi, here is my insurance. ...",
  "attachments": [
    {"filename": "document(3).pdf", "text": "CERTIFICATE OF INSURANCE\nInsured person: Lena Fischer ..."}
  ]
}
```

- PDF text is extracted with `pypdf` and cut to the first 2000 characters per attachment, to keep requests small.
- Attachments that aren't PDFs are listed with an empty `text`.
- Only the plain-text body is read. An email sent as HTML only returns an empty `body`.

#### `save_attachment(email_filename, attachment_filename, surname, name, doc_type, academic_year) -> dict`

| Parameter | Example | Rule |
|---|---|---|
| `email_filename` | `email_03.eml` | Must be in `inbox/` |
| `attachment_filename` | `document(3).pdf` | Must match an attachment in that email exactly |
| `surname` | `Fischer` | Unsafe characters removed; spaces become `-` |
| `name` | `Lena` | Same as `surname` |
| `doc_type` | `Insurance` | Must be one of the 4 types in `DOC_TYPES` |
| `academic_year` | `2026-27` | Must match `YYYY-YY` |

On success it returns `{"status": "saved", "path": "filed\\Fischer_Lena\\Fischer_Lena_Insurance_2026-27.pdf"}`. It creates the student folder if needed and **overwrites** a file that has the same name.

#### `append_row(surname, name, host_university, start_date, end_date, documents_received) -> dict`

| Parameter | Example | Notes |
|---|---|---|
| `surname`, `name` | `Fischer`, `Lena` | Stored as `"Fischer Lena"` |
| `host_university` | `Universidad de Granada` | `""` if unknown |
| `start_date`, `end_date` | `2026-09-15` | `YYYY-MM-DD`, or `""` if unknown |
| `documents_received` | `LearningAgreement, Insurance` | Comma-separated |

Behaviour:
- Creates `students.xlsx` with a header row the first time it's called.
- If a row with the same name already exists (case-insensitive), it **updates** that row instead of adding a new one. Non-empty values replace old ones, empty values leave them alone, and the document lists are **merged**, sorted and de-duplicated.
- Returns `{"status": "added" | "updated", "student": "Fischer Lena"}`.
- A `threading.Lock` stops two calls running at the same time from overwriting each other.
- If Excel has the file open, it returns an error asking you to close it.

#### `reply_to_student(email_filename, answer) -> dict`

| Parameter | Description |
|---|---|
| `email_filename` | The `.eml` file the question came from |
| `answer` | The full reply, from "Dear …," to "Kind regards, Erasmus Office" |

- For Gmail emails (`gmail_<id>.eml`), it **sends** a reply to the sender, in the same conversation, with `Re:` in the subject, and returns `{"status": "sent", "to": ...}`.
- It saves the reply in **Gmail Drafts** instead, returning `{"status": "drafted", "reason": ...}`, when:
  - `AUTO_SEND = False` in `gmail_client.py`;
  - the email was sent by a machine (`Auto-Submitted` header, or `Precedence: bulk/list/junk/auto_reply`). This prevents endless loops between two auto-replies;
  - the email came from this mailbox's own address;
  - the conversation already contains a reply from this mailbox. This prevents double replies when a failed run is retried.
- For local test emails, it never sends: it writes `drafts/<email>_reply.txt`, so version 1 works without Gmail.

#### Private helpers

The leading `_` keeps these out of the agent's reach.

- `_load(filename)` opens an `.eml` from `inbox/`. Calling `Path(filename).name` throws away any folder part, so `../../x` can't escape the folder.
- `_clean(text)` keeps letters (accents included), digits, `-` and `_`.

### 3.3 `erasmus_inbox/faq.txt`

Plain-text questions and answers, added to the end of the instruction. It's the agent's **only** source of truth for student questions. The current topics are: grant payment, the Certificate of Arrival deadline, required insurance, changing the Learning Agreement, extending a stay and office hours. All contact details in it are placeholders (`example.edu`).

### 3.4 `erasmus_inbox/make_samples.py`

Creates `inbox/email_01.eml` to `email_08.eml`, each with a one-page PDF made with `fpdf2`. The data is invented, and the cases are chosen to test the agent:

- random attachment names (`IMG_20260611_0931.pdf`, `document(3).pdf`, `Scan 12.pdf`);
- different year formats (`2026/2027`, `2025-2026`, `2026/27`, `2026-27`);
- different date formats (`15/09/2026`, `01.02.2026`, `2026-09-01`, `2 February 2026`);
- names written in different ways (`FISCHER, Lena`, `NOVAK Sofia`, `Rossi, Marco`);
- three students who send two emails each, to test one row per student;
- one question the FAQ answers and one it doesn't.

Running it again overwrites the same 8 files.

### 3.5 `erasmus_inbox/.env` and `__init__.py`

Both were created by `adk create`. ADK loads `.env` automatically. `GOOGLE_GENAI_USE_ENTERPRISE=0` selects Google AI Studio (API-key access) instead of Google Cloud. `__init__.py` imports `agent.py` so ADK can find `root_agent`.

## 4. Data conventions

### Document types

| `doc_type` | Real-world document |
|---|---|
| `LearningAgreement` | Study plan signed by the student, home and host universities |
| `Transcript` | Transcript of Records: grades from the host university |
| `Insurance` | Health, accident or liability insurance certificate |
| `CertificateOfArrival` | Host university's confirmation that the student arrived |

### Academic year

Always `YYYY-YY`: the start year in full, then the last two digits of the end year. The model normalises whatever the document says: `2026/2027`, `2026/27` and `2026-2027` all become `2026-27`.

### File naming

```
filed/<Surname>_<Name>/<Surname>_<Name>_<DocType>_<YYYY-YY>.pdf
```

### `students.xlsx` columns

| Name | Host university | Start date | End date | Documents received |
|---|---|---|---|---|
| Fischer Lena | Universidad de Granada | 2026-09-15 | 2027-01-31 | Insurance, LearningAgreement |

Dates are stored as text in `YYYY-MM-DD` format.

## 5. Processing walkthrough

What happens after you send *"Process the inbox"*:

1. Gemini calls `list_emails` and gets 8 file names.
2. Gemini calls `read_email` once per email, often several at once.
3. For each attachment, Gemini decides the student, type and year from the PDF text first, then from the email, and calls `save_attachment`. If a tool returns an error, such as a badly formatted year, Gemini corrects it and tries again.
4. After all emails are read, Gemini calls `append_row` once per student, combining what it learned from all of that student's emails.
5. Gemini writes a summary table (email → student → document type → saved file), followed by any questions found in the emails, each with its answer.

A run makes about 22 tool calls and usually takes 30 seconds to 2 minutes, depending on the Gemini free-tier rate limits.

## 6. Answering student questions

The instruction tells the model to answer **only** from the FAQ and, when it isn't clearly covered, to reply exactly *"I'll pass this to staff."* This applies both to questions typed in the chat and to questions found inside emails.

| Question | Expected behaviour |
|---|---|
| "When will I get my Erasmus grant?" | Answers from the FAQ |
| "Can I bring my cat to the student dorm?" | "I'll pass this to staff." |
| "Do I need anything else before I leave?" | Could go either way: a partial FAQ answer, or a handover to staff |

In version 1, answers only appear in the chat or in `drafts/`. In version 2, the agent sends them to the student automatically, unless one of the safety rules in `reply_to_student` applies or `AUTO_SEND` is turned off.

## 7. Safety and privacy design

| Risk | Mitigation |
|---|---|
| An email tells the agent to do something else (prompt injection) | The instruction says text in emails and PDFs is data, never instructions. The tools can't send, delete or reach outside the project. |
| A file name tries to escape the folder (`../../`) | `_load` keeps only the bare file name; `_clean` strips unsafe characters from names used in paths |
| Wrong document type or year format | `save_attachment` rejects values that don't match `DOC_TYPES` or `YYYY-YY` |
| Two Excel writes at once | `threading.Lock` in `append_row` |
| API key leak | The key lives only in `.env`, which `.gitignore` excludes from Git |
| The agent emails a student something wrong | Answers come only from the FAQ, otherwise "I'll pass this to staff". Every sent reply is visible in Gmail **Sent**. Set `AUTO_SEND = False` to review everything first. |
| The agent emails someone else | Replies only ever go to the sender of the email being processed, never to an address taken from the email's text |
| Auto-reply loops or double replies | No automatic reply to machine-sent mail, your own address, or a conversation that already has a reply from you |
| The agent reads private mail | Version 2 reads only emails with the Gmail label `Erasmus` |
| Gmail sign-in files leak | `credentials.json` and `token.json` are excluded by `.gitignore`; access can be revoked at myaccount.google.com/permissions |
| Real personal data | All test data is invented; see the free-tier note below |

**Free-tier note:** on the free tier, Google may use the content sent to Gemini to improve its products. Use only fake data, or switch to a paid or institutional setup approved under your university's data-protection (GDPR) rules before processing real student documents.

## 8. Test data and expected results

| Email | Original attachment | Expected saved file |
|---|---|---|
| email_01 | `scan_0042.pdf` | `Fischer_Lena/Fischer_Lena_LearningAgreement_2026-27.pdf` |
| email_02 | `IMG_20260611_0931.pdf` | `Rossi_Marco/Rossi_Marco_Transcript_2025-26.pdf` |
| email_03 | `document(3).pdf` | `Fischer_Lena/Fischer_Lena_Insurance_2026-27.pdf` |
| email_04 | `certif.pdf` | `Demir_Aisha/Demir_Aisha_CertificateOfArrival_2026-27.pdf` |
| email_05 | `LA_final_final.pdf` | `Berg_Jonas/Berg_Jonas_LearningAgreement_2026-27.pdf` |
| email_06 | `file.pdf` | `Novak_Sofia/Novak_Sofia_Insurance_2026-27.pdf` |
| email_07 | `Scan 12.pdf` | `Rossi_Marco/Rossi_Marco_CertificateOfArrival_2025-26.pdf` |
| email_08 | `AD_doc.pdf` | `Demir_Aisha/Demir_Aisha_LearningAgreement_2026-27.pdf` |

Expected `students.xlsx`, with 5 rows. Dates and university names may differ slightly, because the model interprets the documents.

| Name | Host university | Start | End | Documents |
|---|---|---|---|---|
| Fischer Lena | Universidad de Granada | 2026-09-15 | 2027-01-31 | Insurance, LearningAgreement |
| Rossi Marco | Universitat de Barcelona | 2026-02-01 | 2026-06-30 | CertificateOfArrival, Transcript |
| Demir Aisha | University of Warsaw | 2026-09-20 | 2027-02-15 | CertificateOfArrival, LearningAgreement |
| Berg Jonas | Universite de Lyon | 2026-09-01 | 2027-01-20 | LearningAgreement |
| Novak Sofia | Universidade do Porto | (from insurance) | (from insurance) | Insurance |

**Testing the tools without the AI.** From the project folder, with the virtual environment active:

```powershell
python -c "from erasmus_inbox import tools; print(tools.list_emails()); print(tools.read_email('email_01.eml'))"
```

## 9. Customising and extending

| Goal | What to change |
|---|---|
| Edit FAQ answers | `faq.txt`, then restart `adk web`. Avoid `{` and `}`. |
| Use another model | `model=` in `agent.py` |
| Add a document type, such as `Certificate of Attendance` | Add it to `DOC_TYPES` in `tools.py`, to the list in step 2 of `INSTRUCTION` in `agent.py`, and to the `doc_type` docstring in `save_attachment` |
| Add an Excel column | `HEADERS` and the `ws.append([...])` / update logic in `append_row`, plus a new parameter and docstring line |
| Add a new tool | Write a function with type hints and a docstring with an `Args:` section in `tools.py`, then add it to `tools=[...]` in `agent.py` |
| Change the filing pattern | The `folder` and `path` lines in `save_attachment` |

## 10. Limitations

- **Scanned PDFs:** `pypdf` reads only real text. A scanned image returns empty text, so the agent has only the email body to go on.
- **Only PDFs are handled properly:** other attachments (JPG, DOCX) are listed, but `save_attachment` always saves with a `.pdf` extension.
- **HTML-only emails** return an empty body.
- **Students are matched by name only:** two students with the same name share a row, and different spellings (`Muller` and `Müller`) create two rows.
- **Overwrites:** a second document of the same type and year, such as a corrected Learning Agreement, replaces the earlier file.
- **Version 1 marks nothing as processed:** each run processes the whole inbox again. Version 2 labels each handled email `Erasmus/Processed`. This is safe, because files are overwritten and rows updated rather than duplicated, but it's slower.
- **PDF text is truncated** to 2000 characters per attachment.
- **The model can make mistakes.** Staff should review the summary table, especially for unusual documents.
- **Free-tier limits** can stop the agent (error `429`). Each model has a daily request limit per project (for example 20 a day for `gemini-3.5-flash`), and each email uses about 2 requests. The watcher pauses 5 minutes after a `429` instead of retrying every 5 seconds.

## 11. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| The chat shows only your message and no answer | The agent failed to load, for example because `tools.py` is empty or contains a typo. Read the error in the `adk web` window, fix the file, restart `adk web` and open a **New Session**. |
| `running scripts is disabled on this system` | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again |
| `The module '.venv' could not be loaded` | `.venv` doesn't exist yet. Run `python -m venv .venv` first. |
| `'adk' is not recognized` | The virtual environment is off. Run `.venv\Scripts\Activate.ps1`. |
| `UnicodeEncodeError: 'charmap' codec` | Windows text encoding problem. Run `$env:PYTHONUTF8 = "1"`. |
| `429` / `RESOURCE_EXHAUSTED` | You hit a free-tier limit. "Per minute" limits clear after a minute. For "per day" limits, wait for the reset shown in the message ("retry in …h"), switch `model=` to another model (each has its own quota), or enable billing. |
| `API key not valid`, `400` or `403` | Fix `GOOGLE_API_KEY` in `.env` and restart `adk web` |
| `students.xlsx is open in Excel` | Close Excel and ask the agent to retry |
| `erasmus_inbox` missing from the menu | Run `adk web` from the folder that **contains** `erasmus_inbox/` |
| Server hangs on start, or `NotImplementedError` | Use `adk web --no-reload` |
| FAQ edits are ignored | Restart `adk web`, because `faq.txt` is read at load time |

## 12. Ideas for next steps

- **Other mailboxes:** version 2 supports Gmail. Outlook or Microsoft 365 would need a `graph_client.py` with the same functions, using Microsoft Graph.
- **Instant delivery:** replace the 5-second polling with Gmail push notifications (`users.watch` with Google Cloud Pub/Sub).
- **Scanned documents:** add OCR (for example Tesseract), or send the PDF directly to Gemini, which can read images.
- **Better matching:** identify students by email address or student ID instead of name.
- **Processed folder:** move each `.eml` to `inbox/done/` after filing.
- **Review queue:** write uncertain cases to a `needs_review.xlsx` sheet instead of guessing.
- **Missing-document report:** a tool that lists which students still owe which documents.
- **Automated evaluation:** use `adk eval` with the 8 sample emails to check accuracy after every change.

## 13. Version 2: live Gmail watcher

Setup steps are in [GMAIL_SETUP.md](GMAIL_SETUP.md). This section explains how it works.

```
 Gmail label "Erasmus"                       watch_gmail.py (every 5 s)
 ┌───────────────────┐  find_new_messages   ┌──────────────────────────────┐
 │ new student email │ ───────────────────► │ download_eml → inbox/gmail_… │
 └───────────────────┘                      │ ADK Runner: same root_agent  │
          ▲                                 │   read_email, save_attachment│
          │ label "Erasmus/Processed"        │   append_row, reply ─────────┼──► reply sent (or Gmail Drafts)
          └──────────────────────────────── │ mark_processed               │
                                            └──────────────────────────────┘
```

**`watch_gmail.py`**
- Loads `.env`, signs in to Gmail, and creates an ADK `InMemoryRunner`: the same agent as in `adk web`, but driven from code.
- Every `POLL_SECONDS` (5), it asks Gmail for new messages. Each one gets a fresh agent session. The watcher reads the email itself (`read_email`) and puts its content in the prompt, marked as data rather than instructions, so the agent can file, update Excel and reply in a **single step**.
- An email is labeled processed **only after** the agent finishes, so errors such as a network failure or a Gemini `503` lead to an automatic retry on the next round.

**`erasmus_inbox/gmail_client.py`**

| Function | What it does |
|---|---|
| `get_service()` | OAuth2 sign-in. The first time, it opens the browser and saves `token.json`; later it reuses and refreshes that token. |
| `find_new_messages()` | Returns the ids of messages labeled `Erasmus` that aren't labeled `Erasmus/Processed`. Creates both labels if they're missing. |
| `download_eml(msg_id)` | Saves the full original email as `inbox/gmail_<id>.eml`, so all version 1 tools work on it unchanged |
| `mark_processed(msg_id)` | Adds the `Erasmus/Processed` label |
| `auto_send_blocker(msg_id, original)` | Returns why sending would be unsafe (switched off, machine-sent, own address, already answered), or `""` if it's fine to send |
| `send_reply(msg_id, original, answer)` | Builds a reply (To, `Re:` subject, `In-Reply-To`) and sends it in the same Gmail conversation |
| `create_draft_reply(msg_id, original, answer)` | Builds the same reply but stores it in Gmail Drafts |
| `AUTO_SEND` | `True` sends replies when it's safe; `False` saves every reply as a draft |

**Permission (OAuth scope):** `gmail.modify` allows reading, labeling, drafting and sending. It doesn't allow permanent deletion. The code only replies to the sender of the email being processed.

**Agent changes:** the instruction now also covers single new emails ("handle only that email") and tells the agent to call `reply_to_student` whenever an email contains a question, and to say whether the reply was sent or drafted.

**Tested** with a fake Gmail service:
- With real Gemini: only labeled mail is picked up, the email is downloaded byte-for-byte, the PDF is filed, the Excel row is updated, the reply lands in the right conversation with the right headers, the email gets labeled processed, and a processed email is never picked up again.
- For auto-send: a normal email gets a sent reply, while auto-replies, mailing lists, your own emails, already-answered conversations and `AUTO_SEND = False` all produce a draft instead.

**Live dashboard** (`dashboard.py` + `dashboard.html`)
- `watch_gmail.py` calls `dashboard.start()`, which serves a FastAPI app with uvicorn in a background thread on `127.0.0.1:8080`.
- The watcher reports progress through `email_received`, `agent_event`, `email_finished`, `email_failed` and `set_watcher`. `agent_event` reads each ADK event: a call to `reply_to_student` stores the reply text; the results of `save_attachment`, `append_row` and `reply_to_student` mark the steps *PDF filed*, *Excel* and *Reply* (`sent` or `drafted`). Steps an email didn't need become `skipped`.
- The state is saved to `erasmus_inbox/activity.json` after every change, so the history survives restarts. An email that was halfway through when the watcher stopped is shown as failed, and it's retried.

| Endpoint | Returns |
|---|---|
| `GET /` | the page (`dashboard.html`); it polls `/api/state` every 2 seconds |
| `GET /api/state` | watcher status, the newest 50 emails with their steps, the list of filed PDFs, and the rows of `students.xlsx` |
| `GET /files/<student>/<file>.pdf` | a filed PDF; anything outside `filed/` or not a PDF gets 404 |
| `GET /students.xlsx` | the spreadsheet as a download |

Security: the server listens only on `127.0.0.1`, so other computers can't open it. The page inserts all email text as escaped plain text, so a crafted subject line can't inject HTML or scripts.

Tested with a fake Gmail and a scripted agent that called the real tools: a sent reply, a drafted reply, and a quota failure followed by a successful retry. The page showed each state correctly, PDF and Excel links opened, path-traversal attempts returned 404, and the layout fit a 375-pixel phone screen.

**Speed** (measured with `gemini-3.5-flash` on one email containing a PDF and a question; the lite model answered a short test in about 3 s):

| | Before tuning | After tuning |
|---|---|---|
| Wait for the next Gmail check | 0 to 30 s (polling every 30 s) | 0 to 5 s (polling every 5 s) |
| Gemini round trips | 3 | 2 (email content in the prompt; all actions in one step) |
| Processing | 15.1 s | 10.5 to 13.4 s (also `thinking_level="low"`) |
| **Total, label to reply** | **about 15 to 45 s** | **about 11 to 18 s** |

**Limits of version 2:**
- It checks every 5 seconds rather than instantly.
- It checks the newest 100 labeled emails per round.
- Students are still matched by name.
- With an External consent screen in "Testing" mode, Google asks you to sign in again every 7 days.

## 14. Glossary

| Term | Meaning |
|---|---|
| **OAuth2** | Google's "Sign in → Allow" system: you give a program permission to use your account without sharing your password |
| **OAuth client / `credentials.json`** | The ID card of your program, created in Google Cloud |
| **`token.json`** | The saved permission you gave after clicking "Allow" |
| **Gmail label** | A tag on an email, like a folder; an email can have several |
| **Polling** | Checking for something new at regular intervals (here every 5 seconds) |
| **Draft** | An email that is written but not sent, waiting in Gmail Drafts |
| **Auto-reply loop** | Two automatic responders answering each other forever; prevented by never auto-replying to machine-sent mail |
| **Agent** | An AI model that can decide by itself to call tools to complete a task |
| **ADK** | Agent Development Kit: Google's Python toolkit for building agents |
| **Tool** | A Python function the agent is allowed to call |
| **Model / LLM** | The AI "brain" (here Gemini) that reads text and decides what to do |
| **Instruction / system prompt** | Standing orders the model follows in every conversation |
| **API key** | A secret password that lets your program use Gemini |
| **`.env`** | A file of secret settings that ADK loads automatically |
| **`.eml`** | A single email saved as a file |
| **Virtual environment** | A private set of Python libraries for one project |
| **pip** | Python's tool for installing libraries |
| **localhost:8000** | A web server running on your own computer, on port 8000 |
| **Event** | One step in a conversation (a message, a tool call or a tool result), shown in the ADK web UI |
| **Prompt injection** | Text inside data that tries to give the AI new instructions |
