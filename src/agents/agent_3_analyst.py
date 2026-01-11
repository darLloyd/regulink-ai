import sys
import os
import json
import logging
import time
import pandas as pd
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

# --- CONFIGURATION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

# Load environment variables
load_dotenv(os.path.join(project_root, '.env'))

# Directories
PROCESSED_DIR = os.path.join(project_root, 'data', 'processed')
INTELLIGENCE_DIR = os.path.join(project_root, 'data', 'intelligence')
REPORT_FILE = os.path.join(project_root, 'data', 'intelligence_report.csv')

os.makedirs(INTELLIGENCE_DIR, exist_ok=True)

# --- API SETUP ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ENGINE = "MOCK"
if GEMINI_API_KEY:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    ENGINE = "GEMINI"
elif OPENAI_API_KEY:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    ENGINE = "OPENAI"

# --- JUNK FILTER CONFIGURATION ---
# If any of these phrases appear in the text, we assume it's a failed scrape.
BLOCK_PHRASES = [
    "access denied",
    "security check",
    "challenge-response",
    "verify you are human",
    "cloudflare",
    "403 forbidden",
    "suspected bot activity",
    "enable javascript",
    "captcha",
    "unusual traffic",
    "access to this page has been denied",
    "vpn/proxy",
    "malicious activity detected",
    "malicious behavior detected"

]

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(project_root, 'logs', 'analyst.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Analyst")

class AnalystAgent:
    def __init__(self):
        logger.info(f"🧠 Analyst Agent initialized in {ENGINE} MODE")
        if ENGINE == "MOCK":
            logger.warning("⚠️ No API keys found! Running in simulation mode.")

    def run(self):
        if not os.path.exists(PROCESSED_DIR):
            logger.error(f"❌ Processed directory not found: {PROCESSED_DIR}")
            return

        files = [f for f in os.listdir(PROCESSED_DIR) if f.endswith('.json')]
        
        if not files:
            logger.warning("⚠️ No processed files found. Run Agent 2 first!")
            return

        logger.info(f"📂 Found {len(files)} articles to analyze.")
        
        results = []

        for filename in files:
            file_path = os.path.join(PROCESSED_DIR, filename)
            output_path = os.path.join(INTELLIGENCE_DIR, filename)

            # Idempotency check
            if os.path.exists(output_path):
                try:
                    with open(output_path, 'r', encoding='utf-8') as f:
                        results.append(json.load(f))
                except json.JSONDecodeError:
                    logger.error(f"❌ Corrupted output file: {filename}")
                continue

            # Load Content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"❌ Corrupted input file: {filename}")
                continue

            content = data.get('content_clean', '')
            source = data.get('source', 'Unknown')
            url = data.get('url', '') 

            # --- FILTER 1: Length Check ---
            if not content or len(content) < 100:
                logger.warning(f"⚠️ Skipping {filename}: Content too short.")
                continue

            # --- FILTER 2: Junk/Block Page Check ---
            if any(phrase in content.lower() for phrase in BLOCK_PHRASES):
                logger.warning(f"🛑 Skipping {filename}: Detected 'Access Denied' or Bot Block page.")
                continue

            logger.info(f"🧠 Analyzing: {source}...")

            # Generate Intelligence
            try:
                if ENGINE == "GEMINI":
                    analysis = self._analyze_with_gemini(content)
                elif ENGINE == "OPENAI":
                    analysis = self._analyze_with_openai(content)
                else:
                    analysis = self._mock_analysis(content)
                
                # Validation
                required_keys = ["summary", "impact_score", "tags", "date"]
                if not all(k in analysis for k in required_keys):
                    logger.warning(f"⚠️ Analysis missing keys: {analysis.keys()}")

                # Merge
                full_report = {
                    **data, 
                    **analysis, 
                    "analyzed_at": datetime.now().isoformat(),
                    "engine": ENGINE
                }
                
                # Save Report
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(full_report, f, ensure_ascii=False, indent=4)
                
                results.append(full_report)
                logger.info(f"   ✅ Insight generated.")
                
                # Sleep to avoid rate limits
                time.sleep(4) 

            except Exception as e:
                logger.error(f"   ❌ Analysis failed for {filename}: {e}")

        self._generate_csv_report(results)

    def _generate_csv_report(self, results):
        if not results: return

        df = pd.DataFrame(results)
        priority_cols = ['date', 'source', 'impact_score', 'summary', 'tags', 'url']
        existing_priority = [c for c in priority_cols if c in df.columns]
        other_cols = [c for c in df.columns if c not in existing_priority]
        df = df[existing_priority + other_cols]
        
        if 'impact_score' in df.columns:
            df = df.sort_values(by='impact_score', ascending=False)

        df.to_csv(REPORT_FILE, index=False)
        logger.info(f"📊 Global Report updated: {REPORT_FILE}")
        logger.info(f"🚀 Total Intelligence Items: {len(df)}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    def _analyze_with_gemini(self, text):
        truncated_text = text[:30000]
        # Use stable Flash model
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        
        prompt = """
        You are a Senior Crypto Compliance Officer. 
        Analyze the following regulatory text.
        
        CRITICAL:
        - If the text is about US regulation (SEC/CFTC) with NO impact on EU, set "impact_score": 0.
        
        Return ONLY a JSON object with this exact schema:
        {
            "summary": "One sentence headline.",
            "impact_score": 5,
            "tags": ["Tag1", "Tag2"],
            "date": "YYYY-MM-DD"
        }
        
        Text to analyze:
        """ + truncated_text

        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    def _analyze_with_openai(self, text):
        truncated_text = text[:6000]
        system_prompt = "You are a Senior Crypto Compliance Officer. Output valid JSON."
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": truncated_text}],
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)

    def _mock_analysis(self, text):
        time.sleep(0.5)
        return {
            "summary": "Mock Summary: Regulatory update detected.",
            "impact_score": 5,
            "tags": ["Mock_Tag"],
            "date": datetime.now().strftime('%Y-%m-%d')
        }

if __name__ == "__main__":
    bot = AnalystAgent()
    bot.run()