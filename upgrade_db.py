import json
import os

OLD_PATH = "printers.json"
NEW_PATH = "printers_upgraded.json"

def upgrade_printer_json(old_path, new_path):
    if not os.path.exists(old_path):
        print(f"❌ Could not find file: {old_path}")
        return

    try:
        with open(old_path, 'r') as f:
            data = json.load(f)

        if not isinstance(data, list):
            print("❌ Expected a list format in the original file.")
            return

        upgraded = {
            entry["ip"]: {
                "name": entry.get("name", entry["ip"]),
                "ip": entry["ip"],
                "model": None,
                "serial": None,
                "timestamp": None,
                "toner": {}
            }
            for entry in data if "ip" in entry
        }

        with open(new_path, 'w') as f:
            json.dump(upgraded, f, indent=2)

        print(f"✅ Successfully upgraded format and saved to {new_path}")
    except Exception as e:
        print(f"❌ Failed to convert: {e}")

if __name__ == "__main__":
    upgrade_printer_json(OLD_PATH, NEW_PATH)
