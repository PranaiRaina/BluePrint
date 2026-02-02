import json
import os
from typing import List, Dict, Any

STORE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "failed_extractions_store.json")

# Ensure file exists
if not os.path.exists(STORE_FILE):
    with open(STORE_FILE, "w") as f:
        json.dump([], f)

def load_holdings() -> List[Dict[str, Any]]:
    try:
        if not os.path.exists(STORE_FILE):
             return []
        with open(STORE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading local store: {e}")
        return []

def save_holding(holding: Dict[str, Any]):
    holdings = load_holdings()
    # Add ID and Status
    holding["id"] = f"temp_{len(holdings) + 1}"
    holding["status"] = "pending"
    holding["timestamp"] = "2024-02-01T20:00:00Z" # Mock timestamp or use datetime.now
    
    holdings.append(holding)
    
    with open(STORE_FILE, "w") as f:
        json.dump(holdings, f, indent=2)

def clear_store():
    with open(STORE_FILE, "w") as f:
        json.dump([], f)
