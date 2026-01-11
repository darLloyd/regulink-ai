import os
import sys

# Define the folder structure
structure = {
    "data/raw": {},
    "data/processed": {},
    "logs": {},
    "src/agents": {},
    "src/utils": {},
    "tests": {},
}

# Define initial files to create
files = {
    ".env": "OPENAI_API_KEY=your_key_here\nDATABASE_URL=sqlite:///data/regulink.db",
    ".gitignore": "venv/\n__pycache__/\n*.log\n.env\ndata/raw/*\n.DS_Store",
    "requirements.txt": "pandas\nopenpyxl\nplaywright\nbeautifulsoup4\nfeedparser\ntenacity\nfake-useragent\nsqlalchemy\npython-dotenv",
    "README.md": "# ReguLink AI\n\nAutomated EU Regulatory Intelligence Platform.",
    "src/__init__.py": "",
    "src/config.py": "import os\nfrom pathlib import Path\n\nBASE_DIR = Path(__file__).parent.parent\nDATA_DIR = BASE_DIR / 'data'\nLOG_DIR = BASE_DIR / 'logs'",
    "src/agents/__init__.py": "",
    "src/utils/__init__.py": "",
}

def create_structure():
    print("👷‍♂️ Initializing ReguLink AI Project Structure...")
    
    # Get current working directory
    base_path = os.getcwd()

    # Create Directories
    for folder in structure:
        path = os.path.join(base_path, folder)
        os.makedirs(path, exist_ok=True)
        print(f"   ✅ Created directory: {folder}")

    # Create Files
    for filename, content in files.items():
        path = os.path.join(base_path, filename)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"   ✅ Created file: {filename}")
        else:
            print(f"   ⚠️ File already exists: {filename}")

    print("\n🚀 Foundation built successfully!")
    print("Next Steps:")
    print("1. Open terminal in VS Code.")
    print("2. Run: python -m venv venv")
    print("3. Run: source venv/bin/activate (Mac/Linux) or venv\\Scripts\\activate (Windows)")
    print("4. Run: pip install -r requirements.txt")
    print("5. Run: playwright install")

if __name__ == "__main__":
    create_structure()