# Version 2 setup: connect the agent to your Gmail

Version 2 watches a Gmail label called **Erasmus**. Every 5 seconds it checks for new emails under that label, runs the same agent on each one and then:

- files the PDF attachments and updates `students.xlsx`, exactly like version 1;
- **replies automatically** to student questions, in the same conversation. It saves a **draft** instead when sending could be unsafe (auto-replies, mailing lists, your own emails, or a conversation you already answered). To get drafts only, set `AUTO_SEND = False` in `erasmus_inbox/gmail_client.py`;
- adds the label **Erasmus/Processed**, so no email is handled twice.

**Why OAuth2 and not an API key?** An API key only identifies a program; Google never lets it read someone's private mailbox. **OAuth2** is the "Sign in with Google → Allow" screen, where *you* give this program permission to use *your* Gmail. Your Gemini API key in `.env` stays as it is: it's still used for the AI part.

Setting this up takes about 15 minutes, once.

---

## Part A: Create a Google Cloud project and turn on Gmail

1. Open https://console.cloud.google.com/ and sign in with the Google account whose mailbox the agent will read.
2. Click the project picker at the top of the page, then **New project**. Name it `erasmus-inbox` and click **Create**. Make sure the new project is selected in the top bar.
3. Open https://console.cloud.google.com/apis/library/gmail.googleapis.com and click **Enable**.

## Part B: Set up the consent screen

The **consent screen** is the page that asks "Allow Erasmus Inbox Agent to access your Gmail?".

4. In the menu, open **APIs & Services → OAuth consent screen** (newer consoles call it **Google Auth Platform**), then click **Get started**.
   - **App name:** `Erasmus Inbox Agent`
   - **User support email** and **Contact email:** your own address
   - **Audience:**
     - **External** if you use a normal @gmail.com account.
     - **Internal** if it's a company Google Workspace account and only colleagues will use it.
   - Accept the policy and click **Create**.
5. If you chose **External**, open **Audience → Test users → Add users** and add the Gmail address the agent will read. Only test users can sign in while the app is in "Testing".

## Part C: Create the OAuth client and download its file

6. Open **Clients** (or **Credentials → Create credentials → OAuth client ID**) and click **Create client**.
   - **Application type:** `Desktop app`
   - **Name:** `erasmus watcher`
   - Click **Create**.
7. Click **Download JSON**. Rename the downloaded file to **`credentials.json`** and move it into the **`erasmus_inbox`** folder, next to `agent.py`.

⚠️ `credentials.json` is a secret, like your API key. The project's `.gitignore` keeps it, and the `token.json` created later, off GitHub. Never email or share them.

## Part D: Create the Gmail label

8. In Gmail, scroll the left menu to **Labels** and click **+**. Create a label named exactly **`Erasmus`**.
9. Optional: let Gmail apply the label automatically. Click the search options icon at the right end of the Gmail search bar, enter a rule such as **To:** `your-erasmus-address` or **Has attachment**, click **Create filter**, tick **Apply the label: Erasmus**, then **Create filter**.

Emails *without* the `Erasmus` label are never read by the agent.

## Part E: Install and run

10. In PowerShell, from the `erasmus-hackathon` folder, with the virtual environment on:

```powershell
pip install -r requirements.txt
python watch_gmail.py
```

11. The first time, your browser opens a Google sign-in page:
    - Pick the account you added as a test user.
    - You'll see **"Google hasn't verified this app"**. That's normal for your own app in testing. Click **Advanced → Go to Erasmus Inbox Agent (unsafe)**.
    - Click **Continue** to allow access.

    The terminal then shows:

```
Watching the Gmail label "Erasmus" every 5s. Ctrl+C to stop.
```

A file `erasmus_inbox/token.json` is created, so you won't have to sign in again next time.

## Part F: Test it

12. From another email account, send your Gmail address an email with a PDF attached and a question, for example *"When will I get my Erasmus grant?"* (you can attach one of the PDFs from `examples/filed/`).
13. In Gmail, put the label **Erasmus** on it, unless your filter already did.
14. Within about 10 to 20 seconds, the watcher prints `New email -> gmail_<id>.eml` followed by the agent's summary. Then check:
    - `erasmus_inbox/filed/`: the renamed PDF;
    - `erasmus_inbox/students.xlsx`: the student's row;
    - the sender receives a reply, and it also appears in your Gmail **Sent** folder. If you emailed yourself, it waits in **Drafts** instead, because the agent never auto-replies to your own address;
    - the email now also has the label **Erasmus/Processed**.

To stop the watcher, press **Ctrl+C**.

---

## Troubleshooting

| Message | Plain-words fix |
|---|---|
| `FileNotFoundError: ... credentials.json` | The file isn't in `erasmus_inbox/`, or it's still called `client_secret_....json`. Rename and move it. |
| `Error 403: access_denied` in the browser | Your account isn't a test user. Add it in Part B, step 5. |
| `Gmail API has not been used in project ...` | The Gmail API isn't enabled. Do Part A, step 3. |
| `invalid_grant` or `Token has been expired or revoked` | Delete `erasmus_inbox/token.json` and run the watcher again to sign in. With an **External** app in **Testing**, Google makes you sign in again every 7 days. |
| `Problem, will retry in 5s: 503 UNAVAILABLE` | Gemini is overloaded. The watcher retries by itself, and the email stays unprocessed until it succeeds. If it keeps happening, try another model in `model=` in `agent.py`, such as `gemini-flash-lite-latest`. |
| Nothing happens | Check that the email has the label **Erasmus** and not already **Erasmus/Processed**. |

To remove the agent's access to your Gmail at any time, go to https://myaccount.google.com/permissions.

## Privacy

Real student emails contain personal data. On the free Gemini tier, Google may use what you send to improve its products. Before processing real student mail, check with your university's data-protection (GDPR) officer and use a paid or institutional Gemini setup.
