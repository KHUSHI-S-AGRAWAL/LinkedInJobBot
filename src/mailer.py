import smtplib
import socket
import json
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import sys

# Add parent directory to sys.path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import settings

QUEUE_FILE = Path(__file__).resolve().parent.parent / "config" / "pending_queue.json"

def save_to_queue(recipient_email, subject, body_content):
    try:
        queue = []
        if QUEUE_FILE.exists():
            try:
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    queue = json.load(f)
            except Exception:
                queue = []
        
        # Check if already in queue to prevent duplicates
        for item in queue:
            if item.get("recipient_email") == recipient_email and item.get("subject") == subject:
                print(f"[Mailer] Email to {recipient_email} already exists in retry queue. Skipping duplicate.")
                return
                
        queue.append({
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body_content,
            "timestamp": time.time()
        })
        
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=4)
        print(f"[Mailer] Saved email to offline retry queue for {recipient_email} 💾")
    except Exception as e:
        print(f"[Mailer] Failed to save email to queue: {e}")

def retry_pending_emails():
    if not QUEUE_FILE.exists():
        return
        
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            queue = json.load(f)
    except Exception as e:
        print(f"[Mailer] Error reading pending queue: {e}")
        return

    if not queue:
        return

    print(f"[Mailer] Found {len(queue)} pending emails in retry queue. Checking network connectivity...")
    
    # Check connection to see if we are back online
    try:
        socket.create_connection(("smtp.gmail.com", 587), timeout=5)
    except Exception:
        print("[Mailer] Internet connection is still offline. Skipping retry sequence.")
        return

    print("[Mailer] Network connection is active! Commencing automatic re-delivery...")
    
    still_pending = []
    sender_email = settings.GMAIL_EMAIL.strip().replace('"', '').replace("'", "")
    app_password = settings.GMAIL_APP_PASSWORD.strip().replace('"', '').replace("'", "").replace(" ", "")

    for item in queue:
        recruiter_email = item["recipient_email"]
        subject = item["subject"]
        body_content = item["body"]
        
        print(f"[Mailer] Retrying delivery to {recruiter_email}...")
        
        msg = MIMEMultipart()
        msg['From'] = f"Khushi Agrawal <{sender_email}>"
        msg['To'] = recruiter_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_content, 'plain'))

        # Attach Resume PDF
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
            except Exception as e:
                print(f"[Mailer] Failed to attach resume during retry: {e}")

        server = None
        sent_successfully = False
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recruiter_email, msg.as_string())
            print(f"[Mailer] Successfully delivered queued email to {recruiter_email}! ✅")
            sent_successfully = True
        except Exception as smtp_err:
            print(f"[Mailer] Retry failed for {recruiter_email}: {smtp_err}")
        finally:
            if server:
                try:
                    server.quit()
                except:
                    pass
                    
        if not sent_successfully:
            still_pending.append(item)
            
    # Update queue file
    try:
        if still_pending:
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(still_pending, f, indent=4)
        else:
            if QUEUE_FILE.exists():
                QUEUE_FILE.unlink()
            print("[Mailer] All queued emails delivered successfully! Retry queue is now empty. 🎉")
    except Exception as e:
        print(f"[Mailer] Failed to update queue file: {e}")

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
        # Save to queue on failure
        save_to_queue(recruiter_email, msg['Subject'], body)
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
        # Save to queue on failure
        save_to_queue(recruiter_email, subject, body_content)
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
