import os
import sys
import time
import requests
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from pypdf import PdfReader

# Include project root in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from config import settings
from config.templates import TEMPLATES
from src.scraper import run_post_scraper
from src.mailer import send_custom_email
from src.logger import log_message

app = Flask(__name__)
app.secret_key = "linkedin_job_bot_secret_key"

# Ensure config directory exists
(BASE_DIR / "config").mkdir(exist_ok=True)
LOG_FILE = BASE_DIR / "config" / "run.log"

# Global Threading Lock to prevent overlapping concurrent Gemini API calls
api_generation_lock = threading.Lock()

def extract_text_from_pdf(pdf_path):
    """
    Reads an uploaded PDF file and extracts all raw text content.
    """
    if not Path(pdf_path).exists():
        return ""
    try:
        reader = PdfReader(pdf_path)
        text_content = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_content += text + "\n"
        return text_content.strip()
    except Exception as e:
        log_message(f"Error reading PDF file: {e}")
        return ""

def verify_search_intent_match(search_keyword, extracted_resume_text):
    """
    Validates if the user's target search keyword aligns with their uploaded resume
    before any browser scraping or heavy operations take place.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "None" or not extracted_resume_text:
        return True # Default to True if no key or resume text
        
    prompt = f"""
    You are a Pre-Flight System Gatekeeper for a job search automation platform. 
    Analyze the user's intended job search keyword and their raw resume text.
    
    User Search Keyword: "{search_keyword}"
    
    User Resume Text:
    \"\"\"{extracted_resume_text}\"\"\"
    
    Instruction:
    Determine if it makes semantic sense for a person with this resume to search for jobs matching this keyword.
    - If the keyword is completely outside their domain (e.g., resume is purely a Software Engineer, but keyword is "Sales Executive" or "Admission Marketing Manager"), determine it is a MISMATCH.
    - Allow broad flexibility for adjacent entry-level transitions (e.g., a Web Developer searching for "UI/UX Designer" or "Full Stack Developer" is a MATCH).
    
    Respond with exactly one word: 'MATCH' or 'MISMATCH'. Do not include punctuation or chat commentary.
    """
    try:
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={api_key}"
        res = make_gemini_request_with_retry(url, {
            "contents": [{"parts": [{"text": prompt}]}]
        })
        if res and res.status_code == 200:
            verdict = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip().upper()
            return "MATCH" in verdict
    except Exception as e:
        log_message(f"Pre-flight API check warning: {e}")
    return True

LAST_GEMINI_CALL_TIME = 0

def make_gemini_request_with_retry(url, payload, max_retries=2):
    """
    Wraps standard requests.post to handle HTTP 429 Rate Limiting with an automatic 25s backoff.
    Enforces a strict 12-second buffer window between calls to guarantee free-tier compliance.
    """
    global LAST_GEMINI_CALL_TIME
    
    # Enforce minimum delay of 12 seconds between calls to stay under 5 RPM limit
    current_time = time.time()
    time_since_last_call = current_time - LAST_GEMINI_CALL_TIME
    if time_since_last_call < 12.0:
        sleep_needed = 12.0 - time_since_last_call
        log_message(f"⏳ Rate Limit Safety Shield: Pausing for {sleep_needed:.2f}s to guarantee free-tier compliance...")
        time.sleep(sleep_needed)
        
    for attempt in range(max_retries):
        try:
            res = requests.post(url, json=payload, timeout=30)
            if res.status_code == 200:
                LAST_GEMINI_CALL_TIME = time.time()
                return res
            elif res.status_code == 429:
                log_message(f"⚠️ Hit Gemini API Rate Limit (429). Freezing process for 25s to clear the quota bucket... (Attempt {attempt+1}/{max_retries})")
                time.sleep(25)
            else:
                log_message(f"Gemini API Error: HTTP {res.status_code} - {res.text}")
                break
        except Exception as e:
            log_message(f"Gemini Request Exception: {e}. Retrying in 2 seconds...")
            time.sleep(2)
            
    return None

def update_profile_env(updates):
    env_path = BASE_DIR / ".env"
    existing_vars = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    existing_vars[k.strip()] = v.strip()
    
    for k, v in updates.items():
        existing_vars[k] = v
        
    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in existing_vars.items():
            f.write(f"{k}={v}\n")
            
    import dotenv
    dotenv.load_dotenv(env_path, override=True)
    settings.LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", settings.LINKEDIN_EMAIL)
    settings.LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", settings.LINKEDIN_PASSWORD)
    settings.GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", settings.GMAIL_EMAIL)
    settings.GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", settings.GMAIL_APP_PASSWORD)

@app.route("/")
def index():
    candidate_profile = {
        "candidate_name": os.getenv("CANDIDATE_NAME", ""),
        "candidate_phone": os.getenv("CANDIDATE_PHONE", ""),
        "candidate_location": os.getenv("CANDIDATE_LOCATION", ""),
    }
    resume_exists = settings.RESUME_PATH.exists()
    return render_template("index.html", profile=candidate_profile, resume_exists=resume_exists)

@app.route("/api/save_config", methods=["POST"])
def save_config():
    data = request.form
    
    updates = {
        "CANDIDATE_NAME": data.get("candidate_name"),
        "CANDIDATE_PHONE": data.get("candidate_phone"),
        "CANDIDATE_LOCATION": data.get("candidate_location"),
    }
    
    resume_file = request.files.get("resume_file")
    if resume_file and resume_file.filename:
        resume_file.save(settings.RESUME_PATH)
        
    update_profile_env(updates)
    
    return jsonify({"status": "success", "message": "Profile details saved successfully!"})

@app.route("/api/logs")
def get_logs():
    if not LOG_FILE.exists():
        return jsonify({"status": "success", "logs": []})
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = [line.strip() for line in f.readlines()]
        return jsonify({"status": "success", "logs": logs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/api/search", methods=["POST"])
def search():
    if LOG_FILE.exists():
        try:
            open(LOG_FILE, "w").close()
        except Exception:
            pass
            
    data = request.json or {}
    keywords = data.get("keywords", "Java Developer")
    
    import dotenv
    dotenv.load_dotenv(BASE_DIR / ".env", override=True)
    settings.LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", settings.LINKEDIN_EMAIL)
    settings.LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", settings.LINKEDIN_PASSWORD)
    settings.GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", settings.GMAIL_EMAIL)
    settings.GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", settings.GMAIL_APP_PASSWORD)
    
    log_message(f"Starting Jobs Board search for: Keywords='{keywords}'")
    
    # 1. Extract raw resume text instantly
    resume_text = extract_text_from_pdf(settings.RESUME_PATH)
    
    # 2. Run the instant Pre-Flight Check (No browser required!)
    is_valid_intent = verify_search_intent_match(keywords, resume_text)
    
    if not is_valid_intent:
        log_message(f"🛑 Pre-flight block: Search keyword '{keywords}' does not match candidate domain.")
        return jsonify({
            "status": "blocked",
            "message": f"Your uploaded resume does not match the target job requirements for '{keywords}' searches."
        })

    log_message(f"Pre-flight check passed for '{keywords}'. Launching background automation... 🚀")
        
    keywords_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]
    query = " ".join([f'"{kw}"' for kw in keywords_list])
    
    try:
        posts = run_post_scraper(query, headless=True)
        log_message(f"Search complete. Found {len(posts)} jobs with active recruiter emails.")
        return jsonify({"status": "success", "posts": posts})
    except Exception as e:
        log_message(f"Scraper encountered error: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route("/api/generate_email", methods=["POST"])
def generate_email():
    # Force requests to wait in line sequentially to prevent parallel Gemini requests
    with api_generation_lock:
        time.sleep(2.0)  # Give a 2-second buffer window to let rate limits settle
        
        data = request.json or {}
        post_snippet = data.get("post_snippet", "")
        job_title = data.get("title", "Web Developer")
        company_name = data.get("company", "Company")
        
        candidate_name = os.getenv("CANDIDATE_NAME", "Khushi Agrawal")
        candidate_location = os.getenv("CANDIDATE_LOCATION", "Remote")
        
        candidate_email = os.getenv("GMAIL_EMAIL")
        if not candidate_email or candidate_email == "None":
            candidate_email = settings.GMAIL_EMAIL
        if not candidate_email or candidate_email == "None":
            candidate_email = ""
            
        candidate_phone = os.getenv("CANDIDATE_PHONE", "")
        if not candidate_phone or candidate_phone == "None":
            candidate_phone = ""
            
        # --- Try Gemini AI Email Generation with Dynamic PDF Resume Parsing ---
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and api_key != "None":
            # Extract raw text dynamically from the uploaded PDF resume file
            extracted_resume_text = extract_text_from_pdf(settings.RESUME_PATH)
            
            # Build candidate metadata
            candidate_context = f"""
            Candidate Contact Metadata:
            - Name: {candidate_name}
            - Phone: {candidate_phone}
            - Location Preference: {candidate_location}
            - Email: {candidate_email}
            - Availability: Immediate / Remote Open
            """
            
            subject_prompt = f"Create a short, professional email subject line for an application matching the job: '{job_title}' at '{company_name}'. Return ONLY the subject line text. Do not wrap in quotes."
            body_prompt = f"""
            You are an elite career assistant module for an automated job application platform. 
            Write a short, professional, direct cold email applying for a job.
            
            Target Job Title: {job_title}
            Target Company: {company_name}
            
            Applicant's Raw Resume Data:
            \"\"\"{extracted_resume_text}\"\"\"
            
            Strict Design Rules:
            1. Direct Intent: State clearly in the first sentence that the applicant is applying for the '{job_title}' position at '{company_name}'.
            2. NO Echoing: Do NOT quote or reference text blocks, snippets, role descriptions, headers, location requirements, or salary numbers from the job description. The recruiter already knows what the job details are.
            3. Profile Extraction: Dynamically extract the applicant's real name and contact information directly from the provided Resume Data. Do NOT invent names or use old placeholder strings. Ensure the name '{candidate_name}' is used at the sign-off if the resume text lacks it.
            4. Short Summary: Briefly mention 2 or 3 core technical or professional skill sets from the user's resume that match the job field to show competence, then state that their professional resume is attached as a PDF.
            5. Length: Keep the entire email under 120 words. No boilerplate fluff.
            6. Output Format: Return ONLY the raw body text of the email. Do not include markdown brackets, code blocks, or subject lines.
            """
            
            try:
                subject_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={api_key}"
                
                # Generate Subject with retry wrapper
                res_sub = make_gemini_request_with_retry(subject_url, {
                    "contents": [{"parts": [{"text": subject_prompt}]}]
                })
                ai_subject = f"Application: {candidate_name} - Job Inquiry"
                if res_sub and res_sub.status_code == 200:
                    content = res_sub.json()
                    ai_subject = content["candidates"][0]["content"]["parts"][0]["text"].strip().replace('"', '')
                    
                # Generate Body with retry wrapper
                res_body = make_gemini_request_with_retry(subject_url, {
                    "contents": [{"parts": [{"text": body_prompt}]}]
                })
                if res_body and res_body.status_code == 200:
                    content = res_body.json()
                    ai_body = content["candidates"][0]["content"]["parts"][0]["text"].strip()
                    
                    return jsonify({
                        "status": "success",
                        "subject": ai_subject,
                        "body": ai_body
                    })
            except Exception as e:
                log_message(f"Gemini AI generation warning: {e}. Falling back to standard templates.")

        # --- DYNAMIC PROCEDURAL FALLBACK ---
        # If the API completely fails, we assemble a clean email using the job variables
        # rather than a hardcoded static frontend template text string.
        log_message("🚨 Gemini completely unavailable. Deploying dynamic procedural fallback.")
        clean_title = job_title.split("with verification")[0].strip()
        formatted_body = f"""Dear Hiring Manager,

I hope this email finds you well.

I am writing to formally express my interest in the {clean_title} position at {company_name}. Based on my background and interest in executing core responsibilities within this domain, I am confident I can add value to your team.

I have attached my professional resume (PDF) to this email for your review. I would appreciate the opportunity to discuss how my profile aligns with your current requirements.

Thank you for your time and consideration.

Sincerely,

{candidate_name}
Email: {candidate_email}
Phone: {candidate_phone}"""

        subject = f"Application: {candidate_name} - {clean_title} Role"
        
        return jsonify({
            "status": "success",
            "subject": subject,
            "body": formatted_body
        })

@app.route("/api/apply", methods=["POST"])
def apply():
    data = request.json or {}
    recruiter_email = data.get("recruiter_email")
    subject = data.get("subject")
    body = data.get("body")
    
    if not recruiter_email or not subject or not body:
        return jsonify({"status": "error", "message": "Missing email fields."})
        
    # Spin up an isolated background thread to handle SMTP dispatch cleanly without blocking Flask response
    mailer_thread = threading.Thread(
        target=send_custom_email,
        args=(recruiter_email, subject, body)
    )
    mailer_thread.daemon = True
    mailer_thread.start()
    
    return jsonify({
        "status": "success",
        "message": f"Email application pipeline initiated for {recruiter_email} in the background!"
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
