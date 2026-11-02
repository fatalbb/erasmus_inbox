# Example run

Real input and output from one run of the agent, so you can see what it does without installing anything. All people and documents are invented by `make_samples.py`.

| Path | What it is |
|---|---|
| `inbox/` | **Input:** the 8 test emails (`.eml`), each with a PDF attachment with a random name |
| `filed/` | **Output:** the 8 attachments, renamed and sorted into one folder per student |
| `students.xlsx` | **Output:** one row per student |
| `agent_summary.md` | **Output:** the agent's final answer in the chat, with the summary table and the FAQ answers |

## Results

Prompt `Process the inbox`, model `gemini-flash-latest`, ADK 2.13.0.

- **8/8** attachments filed with the correct student, document type and academic year.
- **5/5** students in `students.xlsx`. The three students who sent two emails each have a single merged row.
- **3/3** student questions handled: one answered from the FAQ (grant payment), and two passed to staff ("anything else before I leave?" and "can I bring my cat?").

| Original attachment | Filed as |
|---|---|
| `scan_0042.pdf` | `Fischer_Lena/Fischer_Lena_LearningAgreement_2026-27.pdf` |
| `IMG_20260611_0931.pdf` | `Rossi_Marco/Rossi_Marco_Transcript_2025-26.pdf` |
| `document(3).pdf` | `Fischer_Lena/Fischer_Lena_Insurance_2026-27.pdf` |
| `certif.pdf` | `Demir_Aisha/Demir_Aisha_CertificateOfArrival_2026-27.pdf` |
| `LA_final_final.pdf` | `Berg_Jonas/Berg_Jonas_LearningAgreement_2026-27.pdf` |
| `file.pdf` | `Novak_Sofia/Novak_Sofia_Insurance_2026-27.pdf` |
| `Scan 12.pdf` | `Rossi_Marco/Rossi_Marco_CertificateOfArrival_2025-26.pdf` |
| `AD_doc.pdf` | `Demir_Aisha/Demir_Aisha_LearningAgreement_2026-27.pdf` |

`students.xlsx`:

| Name | Host university | Start date | End date | Documents received |
|---|---|---|---|---|
| Berg Jonas | Universite de Lyon | 2026-09-01 | 2027-01-20 | LearningAgreement |
| Fischer Lena | Universidad de Granada | 2026-09-15 | 2027-01-31 | Insurance, LearningAgreement |
| Novak Sofia | Universidade do Porto | 2027-02-10 | 2027-06-30 | Insurance |
| Rossi Marco | Universitat de Barcelona | 2026-02-01 | 2026-06-30 | CertificateOfArrival, Transcript |
| Demir Aisha | University of Warsaw | 2026-09-20 | 2027-02-15 | CertificateOfArrival, LearningAgreement |

To open an `.eml` file, double-click it on Windows (it opens in Outlook or Mail) or open it in any text editor.
