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
    # Add ID and Status if missing
    if "id" not in holding:
        holding["id"] = f"temp_{len(holdings) + 1}"
    if "status" not in holding:
        holding["status"] = "pending"
    if "timestamp" not in holding:
        from datetime import datetime
        holding["timestamp"] = datetime.now().isoformat()
    
    holdings.append(holding)
    
    with open(STORE_FILE, "w") as f:
        json.dump(holdings, f, indent=2)

def update_holding_status(holding_id: str, new_status: str):
    holdings = load_holdings()
    updated = False
    for item in holdings:
        if item.get("id") == holding_id:
            item["status"] = new_status
            updated = True
            break
    
    if updated:
        with open(STORE_FILE, "w") as f:
            json.dump(holdings, f, indent=2)
    return updated


def save_all_holdings(holdings: List[Dict[str, Any]]):
    """Overwrite entire holdings file (used for delete operations)."""
    with open(STORE_FILE, "w") as f:
        json.dump(holdings, f, indent=2)


def clear_store():
    with open(STORE_FILE, "w") as f:
        json.dump([], f)
