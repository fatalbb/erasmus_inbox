# Erasmus Inbox Agent

An AI agent that helps a university Erasmus office handle its inbox. It reads student emails, recognises each attached document, files it under a consistent name, keeps a spreadsheet of students up to date and answers common student questions from a short FAQ.

Built with Google's [Agent Development Kit (ADK)](https://google.github.io/adk-docs/) and the Gemini model `gemini-3.5-flash`.

There are two ways to run it:
- **Version 1:** process a folder of `.eml` files from the ADK web chat.
- **Version 2:** watch a live Gmail label and handle each new email automatically, including draft replies. See [Version 2](#version-2-live-gmail-watcher).

## What it does

Students send documents with random file names such as `scan_0042.pdf` or `IMG_20260611_0931.pdf`. For every `.eml` file in the inbox, the agent:

1. **Reads** the email and the text inside each PDF attachment.
2. **Works out** the student's name, the document type and the academic year.
3. **Files** the attachment as
   `filed/<Surname_Name>/<Surname>_<Name>_<DocType>_<YYYY-YY>.pdf`
   for example `filed/Fischer_Lena/Fischer_Lena_LearningAgreement_2026-27.pdf`.
4. **Updates** `students.xlsx`, with one row per student: name, host university, start date, end date and documents received.
5. **Answers** questions found in emails or asked in the chat, using only the FAQ. When the FAQ doesn't cover a question, it replies *"I'll pass this to staff."*

Supported document types: `LearningAgreement`, `Transcript`, `Insurance`, `CertificateOfArrival`.

## Project structure

```
erasmus-hackathon/
├── README.md              this file
├── DOCUMENTATION.md       full technical documentation
├── GMAIL_SETUP.md         version 2: step-by-step Google Cloud and Gmail setup
├── watch_gmail.py         version 2: watches Gmail and runs the agent on new mail
├── requirements.txt       Python libraries to install
├── .gitignore             keeps secrets and generated files out of Git
├── examples/              input and output of a real run (fake data)
├── .venv/                 Python virtual environment (not shared)
└── erasmus_inbox/         the agent (ADK loads this folder)
    ├── __init__.py        makes the folder a Python package
    ├── agent.py           agent definition: model, instructions, tools
    ├── tools.py           list_emails, read_email, save_attachment, append_row, draft_reply
    ├── gmail_client.py    version 2: Gmail sign-in, labels, downloads, drafts
    ├── faq.txt            the questions and answers the agent may use
    ├── make_samples.py    generates 8 fake test emails
    ├── .env               your Gemini API key (secret, never share)
    ├── credentials.json   version 2: your OAuth client from Google Cloud (secret)
    ├── token.json         version 2: created after you click "Allow" (secret)
    ├── .gitignore         keeps .env out of Git
    ├── inbox/             .eml files to process
    ├── filed/             created by the agent: renamed PDFs
    ├── drafts/            created by the agent: reply drafts for local test emails
    └── students.xlsx      created by the agent: one row per student
```

## Requirements

- Python 3.10 or newer
- A free Gemini API key from https://aistudio.google.com/apikey
- Tested with google-adk 2.13.0, openpyxl 3.1.5, pypdf 6.21.4 and fpdf2 2.9.0

## Quick start (Windows PowerShell)

Get the code, then run the rest from the project folder:

```powershell
git clone https://github.com/fatalbb/erasmus_inbox.git
cd erasmus_inbox
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"
pip install -r requirements.txt
```

On macOS or Linux, activate with `source .venv/bin/activate` and skip the two lines before and after it.

Create `erasmus_inbox/.env` (or run `adk create erasmus_inbox`, which writes it for you):

```
GOOGLE_GENAI_USE_ENTERPRISE=0
GOOGLE_API_KEY=paste-your-key-here
```

Generate the test emails, then start the web interface:

```powershell
python erasmus_inbox\make_samples.py
adk web
```

Open http://localhost:8000, pick **erasmus_inbox** in the menu at the top left and send:

```
Process the inbox
```

## What you should see

To see the results of a real run without installing anything, look in [examples/](examples/README.md): 8 of 8 documents filed correctly, 5 of 5 students, and 3 of 3 questions handled.

- The chat shows each tool call as it happens: `list_emails`, `read_email` ×8, `save_attachment` ×8 and `append_row` ×5. A full run takes about 30 seconds to 2 minutes.
- At the end there is a summary table and the agent's answers to student questions.
- `erasmus_inbox/filed/` holds 5 student folders containing 8 PDFs.
- `erasmus_inbox/students.xlsx` holds 5 rows. Students who sent two emails still have only one row.

Try asking questions in the chat as well:

| You ask | Expected answer |
|---|---|
| `When will I get my Erasmus grant?` | From the FAQ: 70% within 30 days after the Learning Agreement and Certificate of Arrival are received |
| `Can I do my Erasmus in Japan?` | "I'll pass this to staff." |

To start again from a clean state, delete `erasmus_inbox/filed/` and `erasmus_inbox/students.xlsx`.

## Version 2: live Gmail watcher

`watch_gmail.py` signs in to your Gmail with **OAuth2** and checks the label **Erasmus** every 30 seconds. For each new email it:

1. downloads it into `erasmus_inbox/inbox/` as `gmail_<id>.eml`;
2. runs the same agent on it: it files the PDFs and updates `students.xlsx`;
3. if the email asks a question, writes a **draft reply** in Gmail Drafts. Nothing is sent automatically, so staff check and send each reply;
4. adds the label **Erasmus/Processed**, so the email is never handled twice. If anything fails, such as no internet or an overloaded Gemini, the email stays unprocessed and is retried 30 seconds later.

Gmail access uses OAuth2, because Google doesn't allow API keys to read a private mailbox. The Gemini API key in `.env` is still used for the AI. The app asks for one permission, `gmail.modify` (read, label and create drafts), and the code never sends or deletes email.

**Setup (once, about 15 minutes):** follow [GMAIL_SETUP.md](GMAIL_SETUP.md) to create a Google Cloud OAuth client, save it as `erasmus_inbox/credentials.json` and create the Gmail label. Then:

```powershell
python watch_gmail.py
```

The first run opens your browser so you can click **Allow**. After that, the terminal shows each new email as it's processed. Press Ctrl+C to stop.

Version 1 still works unchanged with `adk web`. There, `draft_reply` saves drafts as text files in `erasmus_inbox/drafts/` instead of Gmail.

## Customising

- **FAQ:** edit `erasmus_inbox/faq.txt` and restart `adk web`. Don't use `{` or `}`, because ADK treats them as placeholders.
- **Model:** change `model=` in `erasmus_inbox/agent.py`.
- **New document type:** add it to `DOC_TYPES` in `tools.py` and to the list in the instruction in `agent.py`.

See [DOCUMENTATION.md](DOCUMENTATION.md) for how everything works, its limitations and troubleshooting.

## Security and privacy

- **Never commit `erasmus_inbox/.env`.** It contains your API key.
- The root `.gitignore` keeps `.env`, `credentials.json`, `token.json`, `.venv/`, ADK session data, `inbox/`, `filed/`, `drafts/` and `students.xlsx` out of Git, so no key, Google sign-in file or student document is ever committed. After cloning, recreate the test emails with `make_samples.py`.
- All sample data is invented. Don't process real student documents on the free Gemini tier without checking your university's data-protection (GDPR) rules first, because Google may use free-tier content to improve its products.
- The agent treats text in emails and PDFs as data, never as instructions. Its tools can only read from `inbox/` and write inside `filed/` and `students.xlsx`.
