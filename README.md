# 🚀 Automated LinkedIn Recruiter Bot & Smart Mailer Pipeline

An autonomous job application workflow engine built using **Flask** and **Playwright**. The system parses active frontend and web developer job cards directly from a live LinkedIn search feed, extracts relevant business properties, queries the **Hunter.io API** to locate target corporate recruiters, and dispatches custom tailored cover letters with a local resume attachment via secure **SMTP TLS handshakes**.

---

## 🏗️ Architectural Topology & System Flow

1. **Initialization:** The user sets parameters and uploads a resume PDF via the web interface.
2. **Session Injection:** Playwright launches a headless browser, injecting session cookies to bypass login walls.
3. **Extraction & Enrichment:** The bot parses left-hand list components, matches corporate entities via Hunter.io API.
4. **AI Generation:** The system passes data to Gemini API or triggers dynamic procedural fallbacks.
5. **SMTP Mailer:** The background thread authenticates with Google SMTP to deliver the multi-part payload.

---

## 🛠️ Local Sandbox Setup Guide

### 1. Prerequisites
Ensure you have the following installed on your host system:
* Python 3.10 or higher
* Google Chrome or Chromium browser tracking layers

### 2. Repository Cloning & Dependency Mapping
Clone the repository and jump into the working project container root:
```bash
git clone https://github.com/KHUSHI-S-AGRAWAL/LinkedInJobBot.git
cd LinkedInJobBot
```

Instantiate a clean virtual environment and compile the structural dependencies:
```bash
# Create virtual runtime environment
python -m venv venv

# Activate the local sandbox partition (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install core packaging modules
pip install -r requirements.txt

# Download native Playwright system browser binaries
playwright install chromium
```

### 3. Environment Configuration Vault (`.env`)
To protect user credentials, all data vectors are read locally from the environment block. Duplicate the structural template file:
```bash
cp .env.example .env
```

Open the newly created `.env` file and populate it with your private developer coordinates:
```env
# Core API Gateways
GEMINI_API_KEY=your_gemini_api_key_here
HUNTER_API_KEY=your_hunter_io_api_key_here

# User Authentication Vault (Read locally by background threads)
GMAIL_EMAIL=your_personal_email@gmail.com
GMAIL_APP_PASSWORD=xxxx  # Your 16-character Google App Password (remove spaces)
LINKEDIN_LI_AT_COOKIE=your_raw_li_at_cookie_string
```

> 🔐 **Security Note:** The `.env` wrapper is strictly blacklisted inside `.gitignore` and will never be pushed to the public repository index. All credential processing executes locally on your host environment loop.

### 4. Bypassing Authentication Layers
To extract your active LinkedIn session token:
1. Navigate to LinkedIn on your host web browser and ensure you are logged in.
2. Press `F12` to trigger the **Developer Tools** inspector console.
3. Select the **Application** tab (or **Storage** on Firefox) -> Expand **Cookies** -> Select `https://www.linkedin.com`.
4. Locate the row named **`li_at`**, copy the alphanumeric value string, and paste it directly into your local `.env` file next to `LINKEDIN_LI_AT_COOKIE`.

---

## 🚀 Running the Server Application

Once configuration variables are assigned, boot up the local Flask web development controller:
```bash
python app.py
```
Open your web browser and navigate to `http://127.0.0.1:5000` to interact with the orchestration console panel dashboard interface. All operational metrics will stream directly to your raw developer log component workspace.
