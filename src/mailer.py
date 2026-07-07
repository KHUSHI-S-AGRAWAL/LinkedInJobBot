import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
import sys

import contextlib

# Context manager to temporarily force socket.getaddrinfo to resolve ONLY IPv4 addresses.
# This prevents Windows systems from attempting IPv6 connections (bypassing WinError 10060 connection timeout issues)
# while retaining the "smtp.gmail.com" hostname for valid SSL handshake verification.
# By making this a context manager, we prevent global monkeypatch side-effects (like Gemini API's SSL EOF errors).
@contextlib.contextmanager
def force_ipv4():
    orig_getaddrinfo = socket.getaddrinfo
    def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    socket.getaddrinfo = ipv4_only_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = orig_getaddrinfo

# Add parent directory to sys.path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import settings

def send_recruiter_email(recruiter_email, post_snippet, job_keywords="Java Developer / Contract"):
    print(f"[Mailer] Preparing application email to recruiter: {recruiter_email}...")
    
    if not settings.GMAIL_EMAIL or not settings.GMAIL_APP_PASSWORD:
        print("[Mailer] Error: Gmail credentials are not configured in settings.")
        return False

    msg = MIMEMultipart()
    msg['From'] = settings.GMAIL_EMAIL
    msg['To'] = recruiter_email
    msg['Subject'] = f"Application: {job_keywords} - Job Inquiry"

    body = f"""Dear Hiring Team / Recruiter,

I hope this email finds you well.

I am writing to express my interest in the Java Developer / Contract position that you recently posted on LinkedIn:
"{post_snippet.strip()}"

Please find my candidate details below for your review:

- Position: Java Developer (Contract)
- Work Authorization: Eligible for Contract / C2C / Full-time
- Availability: Immediate (2 Weeks Notice)
- Location: Remote / Relocation open
- Attached Resume: Yes (PDF format)

I have attached my resume to this email. I would appreciate the opportunity to discuss how my background aligns with your client's needs.

Looking forward to hearing from you.

Best regards,
Candidate Name
Email: {settings.GMAIL_EMAIL}
Phone: (123) 456-7890
"""
    msg.attach(MIMEText(body, 'plain'))

    # Attach Resume PDF
    resume_path = Path(settings.RESUME_PATH)
    if resume_path.exists():
        try:
            with open(resume_path, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype="pdf")
                attach.add_header('Content-Disposition', 'attachment', filename=resume_path.name)
                msg.attach(attach)
                print(f"[Mailer] Attached resume: {resume_path.name}")
        except Exception as e:
            print(f"[Mailer] Failed to attach resume: {e}")
    else:
        print(f"[Mailer] Warning: Resume not found at {resume_path}")

    try:
        sender_email = settings.GMAIL_EMAIL.strip().replace('"', '').replace("'", "")
        app_password = settings.GMAIL_APP_PASSWORD.strip().replace('"', '').replace("'", "").replace(" ", "")
        
        print(f"[Mailer] Connecting to SMTP Server smtp.gmail.com on Port 587 (timeout=30, starttls)...")
        with force_ipv4():
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
                server.starttls()  # SSL handshake validates hostname natively
                server.login(sender_email, app_password)
                server.sendmail(sender_email, recruiter_email, msg.as_string())
        print(f"[Mailer] Email successfully sent to {recruiter_email}!")
        return True
    except Exception as e:
        print(f"[Mailer] Failed to send email to {recruiter_email}: {e}")
        return False

def send_custom_email(recruiter_email, subject, body_content):
    print(f"[Mailer] Preparing custom email to recruiter: {recruiter_email}...")
    
    if not settings.GMAIL_EMAIL or not settings.GMAIL_APP_PASSWORD:
        print("[Mailer] Error: Gmail credentials are not configured.")
        return False

    msg = MIMEMultipart()
    msg['From'] = settings.GMAIL_EMAIL
    msg['To'] = recruiter_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body_content, 'plain'))

    # Attach Resume PDF
    resume_path = Path(settings.RESUME_PATH)
    if resume_path.exists():
        try:
            with open(resume_path, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype="pdf")
                attach.add_header('Content-Disposition', 'attachment', filename=resume_path.name)
                msg.attach(attach)
                print(f"[Mailer] Attached resume: {resume_path.name}")
        except Exception as e:
            print(f"[Mailer] Failed to attach resume: {e}")
    else:
        print(f"[Mailer] Warning: Resume not found at {resume_path}")

    try:
        sender_email = settings.GMAIL_EMAIL.strip().replace('"', '').replace("'", "")
        app_password = settings.GMAIL_APP_PASSWORD.strip().replace('"', '').replace("'", "").replace(" ", "")
        
        print(f"[Mailer] Connecting to SMTP Server smtp.gmail.com on Port 587 (timeout=30, starttls)...")
        with force_ipv4():
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
                server.starttls()  # SSL handshake validates hostname natively
                server.login(sender_email, app_password)
                server.sendmail(sender_email, recruiter_email, msg.as_string())
        print(f"[Mailer] Custom email successfully sent to {recruiter_email}!")
        return True
    except Exception as e:
        print(f"[Mailer] Failed to send email to {recruiter_email}: {e}")
        return False

if __name__ == "__main__":
    print("Testing mailer...")
    send_recruiter_email(settings.RECIPIENT_EMAIL, "Looking for Java developers. Send resumes to...", "Java Developer / Contract")
