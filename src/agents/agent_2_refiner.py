import sys
import os
import pandas as pd
import logging
import requests
import trafilatura
import hashlib
import json
import time
import re
from datetime import datetime
from urllib.parse import urlparse
from tenacity import retry, stop_after_attempt, wait_fixed

# --- CONFIGURATION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

DATA_FILE = os.path.join(project_root, 'data', 'EU_Regulatory_Sources_Master.xlsx')
PROCESSED_DIR = os.path.join(project_root, 'data', 'processed')
LOG_FILE = os.path.join(project_root, 'logs', 'refiner.log')

# Ensure directories exist
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Stealth Header
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Refiner")

class RefinerAgent:
    def __init__(self):
        logger.info("🏭 Refiner Agent initialized.")

    def get_url_hash(self, url):
        """Creates a unique filename from a URL (prevents duplicates)."""
        return hashlib.md5(url.encode('utf-8')).hexdigest()

    def is_valid_url(self, url):
        """Basic validation to ensure URL has scheme and netloc."""
        try:
            result = urlparse(str(url))
            return all([result.scheme, result.netloc])
        except:
            return False

    def run(self):
        if not os.path.exists(DATA_FILE):
            logger.error(f"❌ Master file not found at: {DATA_FILE}")
            return

        # --- FIX: Safe File Loading ---
        try:
            ext = os.path.splitext(DATA_FILE)[1].lower()
            if ext == ".xlsx":
                df = pd.read_excel(DATA_FILE)
            elif ext == ".csv":
                df = pd.read_csv(DATA_FILE)
            else:
                logger.error(f"❌ Unsupported file extension: {ext}")
                return
        except Exception as e:
            logger.error(f"❌ Critical Error loading data file: {e}")
            return

        logger.info(f"📂 Scanning {len(df)} sources for content to extract...")
        success_count = 0

        for index, row in df.iterrows():
            source = row.get('Source Name', 'Unknown')
            url = row.get('Target URL', '')
            status = str(row.get('Notes', ''))

            # --- FIX: Strict Status Check via Regex ---
            # Looks for whole words only. "Not Success" will now fail.
            if re.search(r"\b(success|rss ok|scrape ok)\b", status, re.IGNORECASE):
                
                # --- FIX: URL Validation ---
                if self.is_valid_url(url):
                    self.process_url(url, source)
                    success_count += 1
                else:
                    logger.warning(f"    ⚠️ Invalid URL format skipped: {url}")
            else:
                # Optional: log skipped items if debugging
                # logger.debug(f"Skipping {source} (Status: {status})")
                pass

        logger.info(f"✅ Refiner run complete. Processed {success_count} sources.")

    def process_url(self, url, source):
        file_hash = self.get_url_hash(url)
        json_path = os.path.join(PROCESSED_DIR, f"{file_hash}.json")

        # 1. Idempotency Check
        if os.path.exists(json_path):
            logger.info(f"    ⏩ Skipping {source} (Already downloaded).")
            return

        logger.info(f"    ⛏️  Extracting: {source}...")

        try:
            # 2. Download & Clean
            content = self._download_content(url)
            
            # --- FIX: Content Quality Check ---
            # Handles None, empty strings, or very short garbage text
            if not content or len(content) < 50:
                logger.warning(f"      ⚠️ Content too short or empty for {source} ({url})")
                return

            # 3. Save as clean JSON
            data = {
                "source": source,
                "url": url,
                "downloaded_at": datetime.now().isoformat(),
                "content_clean": content
            }

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"      ✅ Saved content to {file_hash}.json")
            
            # Polite delay (configurable via env var, defaults to 1s)
            time.sleep(int(os.getenv("REFINER_DELAY", "1")))

        except Exception as e:
            # --- FIX: Better Error Logging ---
            logger.error(f"      ❌ Failed {source} ({url}): {e}")

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
    def _download_content(self, url):
        """
        Uses Trafilatura to get just the article text.
        Includes timeouts and cleanup.
        """
        try:
            # First try: Trafilatura fetch
            # --- FIX: Added timeout ---
            downloaded = trafilatura.fetch_url(url)
            
            # Fallback: Requests
            if downloaded is None:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                downloaded = resp.text
            
            # Extract main text
            text = trafilatura.extract(downloaded)
            
            # --- FIX: Clean whitespace ---
            if text:
                return text.strip()
            return None

        except Exception as e:
            logger.warning(f"Download Engine Warning ({url}): {e}")
            return None

if __name__ == "__main__":
    bot = RefinerAgent()
    bot.run()