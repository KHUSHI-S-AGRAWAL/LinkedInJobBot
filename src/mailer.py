import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import sys

# Add parent directory to sys.path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import settings

def send_recruiter_email(recruiter_email, post_snippet, job_keywords="Java Developer / Contract"):
    print(f"[Mailer] Preparing application email to recruiter: {recruiter_email}...")
    
    if not settings.GMAIL_EMAIL or not settings.GMAIL_APP_PASSWORD:
        print("[Mailer] Error: Gmail credentials are not configured in settings.")
        return False

    sender_email = settings.GMAIL_EMAIL.strip().replace('"', '').replace("'", "")
    app_password = settings.GMAIL_APP_PASSWORD.strip().replace('"', '').replace("'", "").replace(" ", "")

    msg = MIMEMultipart()
    msg['From'] = f"Khushi Agrawal <{sender_email}>"
    msg['To'] = recruiter_email
    msg['Subject'] = f"Application: Khushi Agrawal - {job_keywords} Role"

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
Khushi Agrawal
Email: {sender_email}
"""
    msg.attach(MIMEText(body, 'plain'))

    # Optimized Resume Attachment Handling
    resume_path = Path(settings.RESUME_PATH)
    if resume_path.exists():
        try:
            with open(resume_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={resume_path.name}",
            )
            msg.attach(part)
            print(f"[Mailer] Attached resume: {resume_path.name}")
        except Exception as e:
            print(f"[Mailer] Failed to attach resume: {e}")
    else:
        print(f"[Mailer] Warning: Resume not found at {resume_path}")

    # Direct, Aggressive Port 587 Connection (No Sequential Lag Loop)
    server = None
    try:
        print(f"[Mailer] Attaching direct stream socket to smtp.gmail.com on Port 587...")
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=30)
        
        server.ehlo()
        server.starttls()
        server.ehlo()
        
        print(f"[Mailer] Authenticating credentials...")
        server.login(sender_email, app_password)
        
        print(f"[Mailer] Dispatches active data bundle stream...")
        server.sendmail(sender_email, recruiter_email, msg.as_string())
        print(f"[Mailer] Email successfully sent to {recruiter_email}!")
        return True
    except Exception as smtp_err:
        print(f"[Mailer] Critical connection block: {smtp_err}")
        return False
    finally:
        if server:
            try:
                server.quit()
            except:
                pass

def send_custom_email(recruiter_email, subject, body_content):
    print(f"[Mailer] Preparing custom email to recruiter: {recruiter_email}...")
    
    if not settings.GMAIL_EMAIL or not settings.GMAIL_APP_PASSWORD:
        print("[Mailer] Error: Gmail credentials are not configured.")
        return False

    sender_email = settings.GMAIL_EMAIL.strip().replace('"', '').replace("'", "")
    app_password = settings.GMAIL_APP_PASSWORD.strip().replace('"', '').replace("'", "").replace(" ", "")

    msg = MIMEMultipart()
    msg['From'] = f"Khushi Agrawal <{sender_email}>"
    msg['To'] = recruiter_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body_content, 'plain'))

    # Optimized Resume Attachment Handling
    resume_path = Path(settings.RESUME_PATH)
    if resume_path.exists():
        try:
            with open(resume_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={resume_path.name}",
            )
            msg.attach(part)
            print(f"[Mailer] Attached resume: {resume_path.name}")
        except Exception as e:
            print(f"[Mailer] Failed to attach resume: {e}")
    else:
        print(f"[Mailer] Warning: Resume not found at {resume_path}")

    # Direct, Aggressive Port 587 Connection (No Sequential Lag Loop)
    server = None
    try:
        print(f"[Mailer] Attaching direct stream socket to smtp.gmail.com on Port 587...")
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=30)
        
        server.ehlo()
        server.starttls()
        server.ehlo()
        
        print(f"[Mailer] Authenticating credentials...")
        server.login(sender_email, app_password)
        
        print(f"[Mailer] Dispatches active data bundle stream...")
        server.sendmail(sender_email, recruiter_email, msg.as_string())
        print(f"[Mailer] Custom email successfully sent to {recruiter_email}!")
        return True
    except Exception as smtp_err:
        print(f"[Mailer] Critical connection block: {smtp_err}")
        return False
    finally:
        if server:
            try:
                server.quit()
            except:
                pass

if __name__ == "__main__":
    print("Testing mailer...")
    send_recruiter_email(settings.RECIPIENT_EMAIL, "Looking for Java developers. Send resumes to...", "Java Developer / Contract")
