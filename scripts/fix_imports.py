import os

ROOT_DIR = "PaperTrader/TradingAgents"

def fix_imports():
    count = 0
    for root, dirs, files in os.walk(ROOT_DIR):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r") as f:
                    content = f.read()
                
                new_content = content.replace("from tradingagents", "from TradingAgents")
                new_content = new_content.replace("import tradingagents", "import TradingAgents")
                
                if new_content != content:
                    print(f"Fixing {path}...")
                    with open(path, "w") as f:
                        f.write(new_content)
                    count += 1
    print(f"Fixed {count} files.")

if __name__ == "__main__":
    fix_imports()
