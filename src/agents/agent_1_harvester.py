import sys
import os
import pandas as pd
import feedparser
import logging
import time
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# --- 1. WINDOWS ENCODING FIX ---
# Forces the console to accept emojis (✅, ❌) without crashing
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

# --- CONFIGURATION ---
DATA_FILENAME = 'EU_Regulatory_Sources_Master.xlsx'
DATA_FILE_PATH = os.path.join(project_root, 'data', DATA_FILENAME)
LOG_DIR = os.path.join(project_root, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Stealth Identity
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "harvester.log"), encoding='utf-8'), # Force UTF-8 for file
        logging.StreamHandler(sys.stdout) # Explicitly use the reconfigured stdout
    ]
)
logger = logging.getLogger("Harvester")

class HarvesterAgent:
    def __init__(self):
        self.browser = None
        self.playwright = None
        self.context = None
        logger.info("🤖 Harvester Agent initialized.")

    def start_browser(self):
        """Starts the Playwright browser instance once."""
        if not self.browser:
            logger.info("🚀 Launching Headless Browser...")
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.context = self.browser.new_context(user_agent=USER_AGENT)

    def stop_browser(self):
        """Closes the browser instance."""
        if self.browser:
            logger.info("🛑 Closing Browser...")
            self.browser.close()
            self.playwright.stop()
            self.browser = None
            self.playwright = None

    def load_data(self):
        if not os.path.exists(DATA_FILE_PATH):
            logger.error(f"❌ Critical: File not found at {DATA_FILE_PATH}")
            return None
        try:
            return pd.read_excel(DATA_FILE_PATH)
        except Exception:
            return pd.read_csv(DATA_FILE_PATH)

    def save_data(self, df):
        try:
            # We skip 'index=False' to avoid permission errors if we can't write, 
            # but usually permissions are the main issue.
            if DATA_FILENAME.endswith('.csv'):
                df.to_csv(DATA_FILE_PATH, index=False)
            else:
                df.to_excel(DATA_FILE_PATH, index=False)
            logger.info(f"💾 Checkpoint saved.")
        except PermissionError:
            # IMPORTANT: We use basic ASCII here to ensure this specific error doesn't crash logging
            logger.error(f"[PERM ERROR] Could not save {DATA_FILENAME}. Please close it in Excel!")
        except Exception as e:
            logger.error(f"Save failed: {e}")

    def run(self):
        df = self.load_data()
        if df is None: return

        logger.info(f"📂 Loaded {len(df)} sources.")
        
        if df['Extraction Strategy'].astype(str).str.contains('scrape', case=False).any():
            self.start_browser()

        try:
            for index, row in df.iterrows():
                source = row.get('Source Name', 'Unknown')
                url = row.get('Target URL', '')
                strategy = str(row.get('Extraction Strategy', '')).lower()
                
                if pd.isna(url) or not url: continue

                logger.info(f"🔎 Processing ({index+1}/{len(df)}): {source}...")
                
                status = "Pending"
                note = ""

                try:
                    if "rss" in strategy:
                        title = self._fetch_rss(url)
                        status = "Success"
                        note = f"RSS OK: {title[:50]}..."
                        # No sleep needed for RSS
                    
                    elif "scrape" in strategy:
                        title = self._scrape_web(url)
                        status = "Success"
                        note = f"Scrape OK: {title[:50]}..."
                        time.sleep(2) # Polite delay
                    
                    elif "api" in strategy:
                        status = "Skipped"
                        note = "API connector not built yet."
                    
                    else:
                        status = "Unknown Strategy"
                        note = f"Strategy '{strategy}' not recognized."

                except Exception as e:
                    status = "Failed"
                    # Clean error message for Excel
                    err_msg = str(e).replace('\n', ' ').replace('\r', '')
                    note = f"Error: {err_msg[:100]}"
                    logger.error(f"   ❌ Error: {err_msg[:100]}...")

                # Update DataFrame
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                df.at[index, 'Notes'] = f"[{timestamp}] {status} - {note}"
                
                if index % 5 == 0: self.save_data(df)

        finally:
            self.stop_browser()
            self.save_data(df)
            logger.info("✅ Run complete.")

    # --- ENGINES ---

    @retry(
        stop=stop_after_attempt(2), 
        wait=wait_exponential(multiplier=1, min=2, max=5),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _fetch_rss(self, url):
        # FIX 3: Pass User-Agent to feedparser to avoid blocking
        feed = feedparser.parse(url, agent=USER_AGENT)
        
        # Handle "Bozo" (Malformed XML) but check entries first
        if not feed.entries:
            # Check if we got a specific HTTP error (like 403 Forbidden)
            if hasattr(feed, 'status') and feed.status >= 400:
                raise ValueError(f"HTTP {feed.status} Error fetching RSS")
            raise ValueError("RSS parsed but found no entries (Empty Feed).")
            
        return feed.entries[0].title

    @retry(
        stop=stop_after_attempt(2), 
        wait=wait_exponential(multiplier=2, min=4, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _scrape_web(self, url):
        if not self.context:
            logger.warning("   ⚠️ Browser context lost. Restarting...")
            self.start_browser()

        page = self.context.new_page()
        try:
            # FIX 4: Handle DNS errors gracefully
            response = page.goto(url, timeout=30000)
            if not response:
                raise ValueError("No response received from server.")
                
            page.wait_for_load_state("domcontentloaded") 
            
            page_title = page.title()
            if not page_title:
                raise ValueError("Page loaded but title was empty.")
            return page_title
        except PlaywrightTimeout:
            raise ValueError("Page load timed out.")
        finally:
            page.close()

if __name__ == "__main__":
    bot = HarvesterAgent()
    bot.run()