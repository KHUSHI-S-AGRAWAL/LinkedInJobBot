import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "config" / "run.log"

def log_message(message):
    """
    Prints a message to terminal and appends it with a timestamp to the web log console file.
    """
    timestamp = datetime.now().strftime('%I:%M:%S %p')
    formatted = f"[{timestamp}] {message}"
    
    # Print to actual console
    print(formatted)
    
    # Write to web console log file
    try:
        # Ensure directory exists
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception as e:
        print(f"[Logger Error] Failed to write to log file: {e}")
