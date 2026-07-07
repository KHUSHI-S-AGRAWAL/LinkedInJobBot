import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if it exists
load_dotenv(BASE_DIR / ".env")

# LinkedIn Credentials
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "your_linkedin_email@example.com")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "your_linkedin_password")

# Gmail Credentials (for sending emails)
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "your_gmail@example.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "your_gmail_app_password")

# Recipient Email for job alert notifications/emails
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", GMAIL_EMAIL)

# Job Search Settings
KEYWORDS = os.getenv("JOB_KEYWORDS", "Software Engineer, Python Developer").split(",")
KEYWORDS = [kw.strip() for kw in KEYWORDS if kw.strip()]
LOCATION = os.getenv("JOB_LOCATION", "Remote")

# Paths
RESUME_PATH = BASE_DIR / "assets" / "resume.pdf"
