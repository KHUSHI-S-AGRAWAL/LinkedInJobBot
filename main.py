import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent))

from config import settings
from src.scraper import run_post_scraper
from src.mailer import send_recruiter_email

def main():
    print("==================================================")
    print("      LINKEDIN RECRUITER POST BOT CONTROL CENTER  ")
    print("==================================================")
    
    # 1. Prompt user interactively for keywords
    keywords_input = input("Enter job keywords (comma-separated, e.g. Java Developer, Contract): ")
    if not keywords_input.strip():
        # Fallback default
        keywords = ["Java Developer", "Contract"]
    else:
        keywords = [kw.strip() for kw in keywords_input.split(",") if kw.strip()]
        
    # 2. Prompt user interactively for location
    location_input = input("Enter location (e.g. Remote, United States) [default: Remote]: ")
    location = location_input.strip() if location_input.strip() else "Remote"
    
    # Construct the search query targeting posts with recruiter emails
    # e.g., ("Java Developer" OR "Contract") AND "Remote" AND ("email" OR "@" OR "send resume")
    keywords_str = " OR ".join([f'"{kw}"' for kw in keywords])
    query = f"({keywords_str}) AND \"{location}\" AND (\"email\" OR \"@\" OR \"send resume\")"

    print("\n==================================================")
    print(f"Search Query: {query}")
    print(f"Resume Attached: {settings.RESUME_PATH} (Exists: {settings.RESUME_PATH.exists()})")
    print("==================================================")
    
    print("\n[System] Starting LinkedIn Post Scraper (last 24 hours)...")
    posts = run_post_scraper(query, headless=False)
    
    if not posts:
        print("\n[System] No matching posts with recruiter emails found.")
        return
        
    print(f"\n[System] Found {len(posts)} posts containing email addresses.")
    
    sent_emails = set()
    success_count = 0
    
    for post in posts:
        author = post.get("author", "Recruiter")
        snippet = post.get("text", "")
        emails = post.get("emails", [])
        
        for email in emails:
            if email in sent_emails:
                continue
            
            # Send application email to recruiter
            if send_recruiter_email(email, snippet, ", ".join(keywords)):
                sent_emails.add(email)
                success_count += 1
                
    print("\n==================================================")
    print(f"Bot execution completed! Sent {success_count} emails to recruiters.")
    print("==================================================")

if __name__ == "__main__":
    main()
