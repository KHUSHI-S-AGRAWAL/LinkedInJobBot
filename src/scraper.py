import sys
import time
import random
import re
import os
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

# Add parent directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import settings
from src.logger import log_message

PROFILE_DIR = Path(__file__).resolve().parent.parent / "config" / "browser_profile"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+-]+\s*(?:@|\[at\]|\(at\)|{at})\s*[a-zA-Z0-9.-]+\s*(?:\.|\[dot\]|\(dot\)|{dot})\s*[a-zA-Z]{2,}",
    re.IGNORECASE
)

def clean_email(email_str):
    email = email_str.replace(" ", "")
    email = re.sub(r"\[at\]|\(at\)|{at}", "@", email, flags=re.IGNORECASE)
    email = re.sub(r"\[dot\]|\(dot\)|{dot}", ".", email, flags=re.IGNORECASE)
    return email

def extract_emails(text):
    matches = EMAIL_REGEX.findall(text)
    emails = {clean_email(m) for m in matches}
    return list(emails)

def extract_text_from_pdf(pdf_path):
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

def block_heavy_assets(route):
    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
        route.abort()
    else:
        route.continue_()

def verify_resume_match(job_title, job_description, extracted_resume_text):
    """
    Compares the user's raw resume text against the target job description.
    Returns True if there is a realistic career/skill overlap, otherwise False.
    Implements a 20-second rate-limiting backoff retry for HTTP 429 errors.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "None" or not extracted_resume_text:
        return True # Default to True if no key or resume text
        
    prompt = f"""
    You are an AI Qualification Validator for a job automation platform. Your job is to strictly analyze if a candidate's resume has a foundational skills match for a target job opening.
    
    Target Job Title: {job_title}
    Target Job Description:
    \"\"\"{job_description}\"\"\"
    
    Candidate's Extracted Resume Text:
    \"\"\"{extracted_resume_text}\"\"\"
    
    Instructions:
    1. Compare the core requirements of the job (e.g., software engineering, marketing, sales, accounting) with the candidate's actual listed background, projects, or education.
    2. If the job description is a complete mismatch for the candidate's domain (e.g., candidate is a Software Engineer, but the job is an On-Site Field Marketing Manager or an accountant), determine that it is NOT a match.
    3. Allow flexibility for general entry-level crossovers or transferable digital fields (like a web developer applying to UI/UX, or a digital marketer applying to a social media content role).
    
    Respond with exactly one word: 'MATCH' or 'MISMATCH'. Do not add punctuation or explanation.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={api_key}"
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            res = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}]
            }, timeout=10)
            
            if res.status_code == 200:
                verdict = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip().upper()
                return "MATCH" in verdict
            elif res.status_code == 429:
                log_message(f"⚠️ verify_resume_match hit Gemini Rate Limit (429). Retrying in 20 seconds... (Attempt {attempt+1}/{max_retries})")
                time.sleep(20)
            else:
                log_message(f"Gemini API mismatch validation warning: HTTP {res.status_code} - {res.text}")
                break
        except Exception as e:
            log_message(f"Error checking resume compatibility: {e}. Retrying in 2 seconds...")
            time.sleep(2)
            
    return True


def query_hunter_api(company_name):
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key or api_key == "your_hunter_api_key_here":
        return None
        
    log_message(f"Querying Hunter.io API for company: '{company_name}'...")
    try:
        url = f"https://api.hunter.io/v2/domain-search?company={company_name}&api_key={api_key}"
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            data = res.json()
            emails_list = data.get("data", {}).get("emails", [])
            
            for item in emails_list:
                position = (item.get("position") or "").lower()
                if any(role in position for role in ["hr", "recruiter", "talent", "acquisition", "hiring", "people"]):
                    email = item.get("value")
                    if email:
                        log_message(f"-> Hunter.io matched HR email: {email} ({item.get('position')})")
                        return email
                        
            if emails_list:
                email = emails_list[0].get("value")
                log_message(f"-> Hunter.io fallback email: {email}")
                return email
        else:
            log_message(f"Hunter.io API returned status: {res.status_code}")
    except Exception as e:
        log_message(f"Hunter.io API query warning: {e}")
    return None

def check_login_state_headless():
    logged_in = False
    import hashlib
    user_identifier = os.getenv("GMAIL_EMAIL", "default").strip().lower()
    email_hash = hashlib.md5(user_identifier.encode()).hexdigest()[:12]
    user_profile_dir = PROFILE_DIR.parent / f"browser_profile_{email_hash}"
    user_profile_dir.mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(user_profile_dir),
                headless=True,
                user_agent=USER_AGENT,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0] if context.pages else context.new_page()
            
            page.goto("https://www.linkedin.com/feed/", timeout=20000, wait_until="commit")
            time.sleep(5)
            
            current_url = page.url
            if "feed" in current_url or "mynetwork" in current_url or "jobs" in current_url:
                logged_in = True
                
            context.close()
        except Exception as e:
            log_message(f"Headless state check error: {e}")
    return logged_in

def check_and_login_linkedin(page, query):
    import urllib.parse
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_query}&f_TPR=r86400"

    log_message("Checking login state by navigating directly to search page...")
    try:
        page.goto(search_url, timeout=30000, wait_until="commit")
        time.sleep(5)
    except Exception:
        pass
    
    current_url = page.url
    if "feed" in current_url or "search" in current_url or "jobs" in current_url:
        log_message("Already logged in! ✅")
        return True
        
    log_message("Session not logged in. Directing to LinkedIn login page...")
    page.goto("https://www.linkedin.com/login", wait_until="commit")
    
    has_creds = settings.LINKEDIN_EMAIL and settings.LINKEDIN_EMAIL != "your_linkedin_email@example.com"
    
    if has_creds:
        try:
            log_message("Attempting auto-fill with credentials...")
            username_selector = "input#username, input[name='session_key'], input[type='text']"
            password_selector = "input#password, input[name='session_password'], input[type='password']"
            
            page.wait_for_selector(username_selector, timeout=5000)
            page.fill(username_selector, settings.LINKEDIN_EMAIL)
            page.fill(password_selector, settings.LINKEDIN_PASSWORD)
            page.click("button[type='submit'], button.btn__primary--large")
            
            time.sleep(5)
            current_url = page.url
            if "feed" in current_url or "search" in current_url or "jobs" in current_url:
                log_message("Logged in automatically! ✅")
                return True
        except Exception:
            log_message("Auto-fill blocked or verification needed.")
            
    log_message("Please log in manually in the open browser window.")
    log_message("Waiting up to 90 seconds for you to complete the login...")
    
    start_time = time.time()
    while time.time() - start_time < 90:
        current_url = page.url
        if "feed" in current_url or "search" in current_url or "jobs" in current_url:
            log_message("Session authenticated successfully! Session saved. ✅")
            return True
        time.sleep(1.5)
        
    log_message("Authentication check timed out.")
    return False

def extract_email_from_profile(context, profile_url):
    if not profile_url or profile_url == "N/A":
        return None
        
    log_message(f"Crawling recruiter profile: {profile_url}")
    page = context.new_page()
    try:
        page.route("**/*", block_heavy_assets)
        page.goto(profile_url, timeout=15000, wait_until="commit")
        time.sleep(3)
        
        body_text = page.inner_text("body")
        emails = extract_emails(body_text)
        if emails:
            page.close()
            return emails[0]
            
        contact_info_selector = "a[href*='/overlay/contact-info/'], #top-card-relationship-strength-info-relationship-strength, a[data-control-name='contact_see_more']"
        contact_button = page.query_selector(contact_info_selector)
        if contact_button:
            contact_button.click()
            time.sleep(1.5)
            
            overlay_text = page.inner_text("body")
            emails = extract_emails(overlay_text)
            if emails:
                page.close()
                return emails[0]
                
            mailto_links = page.query_selector_all("a[href^='mailto:']")
            for link in mailto_links:
                href = link.get_attribute("href")
                if href:
                    email = href.replace("mailto:", "").split("?")[0].strip()
                    if email:
                        page.close()
                        return email
                        
        page.close()
    except Exception as e:
        log_message(f"Recruiter profile crawl warning: {e}")
        try:
            page.close()
        except Exception:
            pass
    return None

def scrape_jobs_board(context, page, query):
    import urllib.parse
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_query}&f_TPR=r86400"
    
    page.route("**/*", block_heavy_assets)
    
    log_message(f"Navigating to Jobs Board: {search_url}")
    try:
        page.goto(search_url, timeout=25000, wait_until="domcontentloaded")
    except Exception as e:
        log_message(f"Jobs Board navigation settled. Proceeding.")
        
    # --- STEP 1: UNIVERSAL TARGET SELECTOR STRATEGY ---
    card_selector = ".jobs-search-results__list-item, .jobs-search-results-list__list-item, .job-card-container, a[href*='/jobs/view/']"

    log_message("⏳ Loading job search feed pane...")
    try:
        page.wait_for_selector(card_selector, timeout=12000)
    except Exception:
        log_message("⚠️ Timeout waiting for job list container. Proceeding anyway.")

    # Scroll down slightly to trigger lazy loading
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 4);")
        time.sleep(2)
    except Exception:
        pass

    # Grab the clean array of physical job cards directly
    job_cards = page.query_selector_all(card_selector)
    
    # Deduplicate cards if we matched raw link tags
    seen_ids = set()
    unique_cards = []
    for card in job_cards:
        try:
            href = card.get_attribute("href")
            if href and "/view/" in href:
                job_id = href.split("/view/")[1].split("/")[0]
                if job_id not in seen_ids:
                    seen_ids.add(job_id)
                    unique_cards.append(card)
            else:
                unique_cards.append(card)
        except Exception:
            unique_cards.append(card)
            
    job_cards = unique_cards
    log_message(f"Found {len(job_cards)} job cards to analyze.")

    # Pre-load the user's resume text for pre-flight checking
    resume_text = extract_text_from_pdf(settings.RESUME_PATH)
    
    jobs_found = []
    hunter_enabled = bool(os.getenv("HUNTER_API_KEY") and os.getenv("HUNTER_API_KEY") != "your_hunter_api_key_here")

    # --- STEP 2: THE DIRECT EXTRACTION LOOP ---
    limit = min(len(job_cards), 15)
    for idx in range(limit):
        # Check if LinkedIn forcefully redirected us away from the jobs page
        if "linkedin.com/jobs" not in page.url:
            log_message("⚠️ Anti-bot redirect detected! Forced onto homepage. Recovery routing initiated...")
            try:
                page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
                try:
                    page.wait_for_selector(card_selector, timeout=12000)
                except Exception:
                    pass
                # Scroll down slightly to trigger lazy load
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 4);")
                    time.sleep(2)
                except Exception:
                    pass
                job_cards = page.query_selector_all(card_selector)
                
                # Deduplicate elements
                seen_ids = set()
                unique_cards = []
                for c in job_cards:
                    try:
                        href = c.get_attribute("href")
                        if href and "/view/" in href:
                            job_id = href.split("/view/")[1].split("/")[0]
                            if job_id not in seen_ids:
                                seen_ids.add(job_id)
                                unique_cards.append(c)
                        else:
                            unique_cards.append(c)
                    except Exception:
                        unique_cards.append(c)
                job_cards = unique_cards
                limit = min(len(job_cards), 15)
            except Exception as recovery_err:
                log_message(f"⚠️ Recovery routing navigation issue: {recovery_err}")
                
            if len(job_cards) == 0 or idx >= len(job_cards):
                log_message("❌ DOM recovery failed. Breaking loop context.")
                break
                
        try:
            card = job_cards[idx]
            
            # Click the card to update the viewport panel view
            try:
                card.scroll_into_view_if_needed()
                card.click(force=True)
                time.sleep(2.5)  # Let dynamic details panel load fully
            except Exception as click_err:
                log_message(f"⚠️ Click operation warning on card {idx+1}: {click_err}")
            
            try:
                page.wait_for_selector(".jobs-description__content, .jobs-box__html-content, #job-details, #job-description", timeout=6000)
            except Exception:
                pass

            # 🎯 Extract Title directly via JS closest selectors
            try:
                job_title = page.evaluate("""(el) => {
                    let tEl = el.querySelector('.job-card-list__title, a.job-card-container__link, .disabled-link-wrapper, .job-card-list__title-link');
                    if (tEl) return tEl.innerText.trim().split('\\n')[0];
                    return el.innerText.trim().split('\\n')[0] || 'Job Opening';
                }""", card)
            except Exception:
                job_title = "Job Opening"
                
            # 🎯 Extract Company Name directly via JS closest ancestor selectors
            try:
                company_name = page.evaluate("""(el) => {
                    let li = el.closest('li') || el.closest('.job-card-container') || el;
                    let compEl = li.querySelector('.job-card-container__company-name, .job-card-list__company-name, .artdeco-entity-lockup__subtitle, .job-card-container__primary-description, [class*="company-name"], [class*="subtitle"]');
                    if (compEl) return compEl.innerText.trim().split('\\n')[0];
                    return 'Company';
                }""", card)
            except Exception:
                company_name = "Company"
                
            if company_name == "Company":
                # Fallback to active right side details panel company selectors
                company_selectors = [
                    ".job-details-jobs-unified-top-card__company-name a",
                    ".jobs-unified-top-card__company-name",
                    ".jobs-details-top-card__company-url",
                    "div.job-details-jobs-unified-top-card__company-name"
                ]
                for selector in company_selectors:
                    try:
                        element = page.query_selector(selector)
                        if element:
                            company_name = element.inner_text().strip().split("\n")[0].strip()
                            break
                    except Exception:
                        continue
            
            # Pull the full text block from the loaded right-hand description box
            description_element = page.query_selector("#job-description, .jobs-description__content, #job-details")
            desc_text = description_element.inner_text().strip() if description_element else ""

            # Fallback if details panel was empty
            if not desc_text:
                desc_text = f"Position for a {job_title} role at {company_name}. Target domain: Web Developer / Design. Full details accessible on the main portal overview data window."
                log_message(f"⚠️ Details panel missing. Deploying local card description context.")

            # Grab job url if needed
            job_url = "N/A"
            try:
                link_el = card.query_selector("a.job-card-list__title, a.job-card-container__link, a[href*='/jobs/view/'], a.job-card-list__title-link")
                href = link_el.get_attribute("href") if link_el else None
                if not href:
                    href = card.get_attribute("href")
                if href:
                    job_url = "https://www.linkedin.com" + href.split("?")[0] if href.startswith("/") else href.split("?")[0]
            except Exception:
                pass

            log_message(f"Analyzing Job {idx + 1}: {job_title} at {company_name}...")
            
            # --- Email Discovery Chain ---
            email = None
            
            emails = extract_emails(desc_text)
            if emails:
                email = emails[0]
                log_message(f"-> Found email inside job description: {email} ✅")
                
            if not email and hunter_enabled:
                email = query_hunter_api(company_name)
                
            if not email and not hunter_enabled:
                poster_link_el = page.query_selector(".jobs-poster__name-link, .jobs-poster__actor a, a[href*='/in/']")
                if poster_link_el:
                    poster_url = poster_link_el.get_attribute("href")
                    if poster_url:
                        poster_url = "https://www.linkedin.com" + poster_url if poster_url.startswith("/") else poster_url
                        email = extract_email_from_profile(context, poster_url)
                        if email:
                            log_message(f"-> Found email via Job Poster profile: {email} ✅")

            if email:
                jobs_found.append({
                    "title": job_title,
                    "author": company_name,
                    "emails": [email],
                    "text": desc_text[:300] + "..." if len(desc_text) > 300 else desc_text,
                    "url": job_url
                })
            else:
                log_message("-> No contact email found for this listing. Skipping.")
                
        except Exception as e:
            if "attached to the DOM" in str(e):
                log_message(f"⚠️ Job card {idx+1} detached from DOM. Attempting emergency element re-fetch...")
                job_cards = page.query_selector_all(".jobs-search-results-list__list-item, .job-card-container, [data-occludable-job-id]")
            else:
                log_message(f"Error parsing job details card: {e}")
            continue
            
    return jobs_found

def run_post_scraper(query, headless=True):
    recruiter_posts = []
    
    li_at_cookie = os.getenv("LINKEDIN_LI_AT_COOKIE")
    if li_at_cookie:
        li_at_cookie = li_at_cookie.strip().replace('"', '').replace("'", "").replace(" ", "")
        
    # Generate an isolated profile directory name based on the unique hash of the GMAIL_EMAIL environment variable.
    # This prevents cookie/session store conflicts when swapping credentials in multi-user test environments.
    import hashlib
    user_identifier = os.getenv("GMAIL_EMAIL", "default").strip().lower()
    email_hash = hashlib.md5(user_identifier.encode()).hexdigest()[:12]
    user_profile_dir = PROFILE_DIR.parent / f"browser_profile_{email_hash}"
    user_profile_dir.mkdir(parents=True, exist_ok=True)
    
    # If a cookie is present, we can validate it in headless mode first
    is_headless = headless
    if li_at_cookie and li_at_cookie != "None" and li_at_cookie != "":
        is_headless = True  # Always start headless for cookie injection
    else:
        li_at_cookie = None
        
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(user_profile_dir),
            headless=is_headless,
            user_agent=USER_AGENT,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        # Inject cookie if configured
        if li_at_cookie and li_at_cookie != "None":
            log_message("Injecting custom LinkedIn li_at session cookie...")
            cookie_payload = {
                "name": "li_at",
                "value": li_at_cookie,
                "domain": ".linkedin.com",
                "path": "/",
                "secure": True,
                "httpOnly": True
            }
            context.add_cookies([cookie_payload])
            
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_query}&f_TPR=r86400"
            
            log_message("Checking LinkedIn authentication session...")
            session_valid = True
            try:
                page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(5)
            except Exception as e:
                log_message(f"⚠️ Navigation redirect block captured: {e}")
                session_valid = False
            
            current_url = page.url
            if not session_valid or "login" in current_url or "checkpoint" in current_url:
                log_message("❌ Session cookie is invalid or expired. Fallback login required.")
                
                # If we are headless, we must close and launch headful browser for manual validation
                if is_headless:
                    page.close()
                    context.close()
                    # Reopen headful
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=str(user_profile_dir),
                        headless=False,
                        user_agent=USER_AGENT,
                        args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
                    )
                    page = context.pages[0] if context.pages else context.new_page()
                    try:
                        page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
                        time.sleep(5)
                    except Exception:
                        pass
                
                if not check_and_login_linkedin(page, query):
                    log_message("Could not log in. Aborting search.")
                    return []
            else:
                log_message("Authenticated successfully via persistent session or cookie injection! ✅")
                
            recruiter_posts = scrape_jobs_board(context, page, query)
        finally:
            context.close()
            
    return recruiter_posts
