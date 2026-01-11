import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load your .env file
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ Error: GEMINI_API_KEY not found in environment.")
else:
    print(f"✅ Found API Key: {api_key[:10]}...")
    
    try:
        genai.configure(api_key=api_key)
        print("\n🔎 Listing available models...")
        
        found_any = False
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"   - {m.name}")
                found_any = True
        
        if not found_any:
            print("⚠️ No models found that support 'generateContent'. Check your API key permissions.")
            
    except Exception as e:
        print(f"\n❌ Error connecting to Google API: {e}")