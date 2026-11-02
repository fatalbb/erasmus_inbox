"""Creates 8 fake test emails with small PDF attachments in inbox/. All people are invented."""
from email.message import EmailMessage
from pathlib import Path

from fpdf import FPDF

INBOX = Path(__file__).parent / "inbox"

# (sender, subject, email body, attachment file name, text inside the PDF)
SAMPLES = [
    ("lena.fischer@student.example.org", "documents",
     "Hello, please find attached my learning agreement. Best, Lena",
     "scan_0042.pdf",
     "LEARNING AGREEMENT - Student Mobility for Studies\nStudent: FISCHER, Lena\n"
     "Academic year: 2026/2027\nReceiving institution: Universidad de Granada\n"
     "Planned mobility: 15/09/2026 to 31/01/2027"),
    ("m.rossi@student.example.org", "Fwd: scan", "see attached",
     "IMG_20260611_0931.pdf",
     "TRANSCRIPT OF RECORDS\nName: Marco Rossi\nHost institution: Universitat de Barcelona\n"
     "Academic year 2025-2026\nData Mining (6 ECTS): A\nSpanish B1 (3 ECTS): B\n"
     "Period of study: 01.02.2026 - 30.06.2026"),
    ("lena.fischer@student.example.org", "insurance",
     "Hi, here is my insurance. Do I need anything else before I leave? Lena Fischer",
     "document(3).pdf",
     "CERTIFICATE OF INSURANCE\nInsured person: Lena Fischer\n"
     "Coverage: health, accident and liability\nValid: 01/09/2026 - 28/02/2027\n"
     "Purpose: Erasmus+ study period 2026-27"),
    ("aisha.demir@student.example.org", "arrived!",
     "Dear office, I arrived safely, attached is the signed certificate. Aisha",
     "certif.pdf",
     "CERTIFICATE OF ARRIVAL\nWe confirm that Ms Aisha Demir\nhas arrived at the University of Warsaw\n"
     "on 22 September 2026\nfor the Erasmus+ study period 2026/27.\nSigned and stamped by the host coordinator."),
    ("jonas.berg@student.example.org", "LA + question",
     "Hello, attached is my LA. When will I get my Erasmus grant? Thanks, Jonas Berg",
     "LA_final_final.pdf",
     "LEARNING AGREEMENT\nStudent name: Jonas Berg\nReceiving institution: Universite de Lyon\n"
     "Study period: 2026-27, winter semester\nStart: 2026-09-01   End: 2027-01-20"),
    ("sofia.novak@student.example.org", "hi",
     "Hi! My insurance is attached. Can I bring my cat to the student dorm in Porto? Sofia",
     "file.pdf",
     "TRAVEL AND HEALTH INSURANCE POLICY\nPolicy holder: NOVAK Sofia\n"
     "Destination: Portugal (Universidade do Porto)\nCover period: 10/02/2027 - 30/06/2027\n"
     "Academic year: 2026/27"),
    ("m.rossi@student.example.org", "arrival", "Sent from my phone",
     "Scan 12.pdf",
     "Certificate of Arrival - Erasmus+\nParticipant: Rossi, Marco\nHost: Universitat de Barcelona\n"
     "Date of arrival: 2 February 2026\nAcademic year: 2025/26"),
    ("aisha.demir@student.example.org", "LA",
     "Learning agreement attached, signed by all parties.",
     "AD_doc.pdf",
     "LEARNING AGREEMENT\nStudent: Demir, Aisha\nReceiving institution: University of Warsaw\n"
     "Mobility period: 20/09/2026 - 15/02/2027\nAcademic year 2026/2027"),
]


def make_pdf(text: str) -> bytes:
    """Builds a one-page PDF containing the given text."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, text)
    return bytes(pdf.output())


INBOX.mkdir(exist_ok=True)
for i, (sender, subject, body, pdf_name, pdf_text) in enumerate(SAMPLES, start=1):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, "erasmus@example.edu", subject
    msg.set_content(body)
    msg.add_attachment(make_pdf(pdf_text), maintype="application", subtype="pdf", filename=pdf_name)
    (INBOX / f"email_{i:02d}.eml").write_bytes(bytes(msg))
print(f"Created {len(SAMPLES)} test emails in {INBOX}")