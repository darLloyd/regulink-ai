import pandas as pd
import os

# Path to your master file
file_path = os.path.join("data", "EU_Regulatory_Sources_Master.xlsx")

if not os.path.exists(file_path):
    print("❌ File not found!")
    exit()

# Load the file
try:
    df = pd.read_excel(file_path)
except:
    df = pd.read_csv(file_path)

# --- THE FIXES ---
# Dictionary of {Source Name: New URL}
updates = {
    # Fix: Point to actual XML, not the landing page
    "European Parliament (Legislative Observatory)": "https://www.europarl.europa.eu/rss/doc/top-stories/en.xml",
    "ECB (Banking Supervision)": "https://www.bankingsupervision.europa.eu/home/rss/html/rss_press.en.xml",
    "BaFin (Germany)": "https://www.bafin.de/SiteGlobals/Functions/RSS/EN/Feed/RSS_Newsfeed_Expert_Articles.xml",
    "CNMV (Spain)": "https://www.cnmv.es/portal/RSS/RSS.aspx?id=1",
    
    # Fix: DNB blocks RSS bots, switch to scraping their news page directly
    "DNB (Netherlands)": "https://www.dnb.nl/en/news/", 
    
    # Fix: EBA changed their feed structure
    "EBA (News & Press)": "https://www.eba.europa.eu/rss.xml"
}

# Apply updates
print("🔧 Applying fixes...")
for source, new_url in updates.items():
    # Update URL
    mask = df['Source Name'] == source
    if mask.any():
        df.loc[mask, 'Target URL'] = new_url
        print(f"   ✅ Updated URL for: {source}")
        
        # Special case for DNB: Change strategy from RSS to Scrape
        if source == "DNB (Netherlands)":
            df.loc[mask, 'Extraction Strategy'] = "Web Scrape"
            print(f"   🔄 Changed Strategy for DNB to 'Web Scrape'")

# Save back
df.to_excel(file_path, index=False)
print("\n💾 Excel file successfully patched. You are ready for Agent 2.")