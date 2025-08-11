# __main__.py
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Import GUI lazily so CLI can run without GUI deps
def run_gui():
    from it_tools.tonertrack import gui
    gui.main()

# --- Shared DB path (matches gui.py) ---
def get_appdata_path(filename: str) -> str:
    appdata_dir = os.path.join(os.getenv("APPDATA"), "TonerTrack")
    os.makedirs(appdata_dir, exist_ok=True)
    return os.path.join(appdata_dir, filename)

DB_FILE = get_appdata_path("printers_upgraded.json")

def load_db() -> dict:
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Failed to read DB: {e}", file=sys.stderr)
        return {}

def save_db(data: dict) -> None:
    try:
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Failed to save DB: {e}", file=sys.stderr)

# --- CLI ops ---
def cmd_list(args):
    data = load_db()
    if not data:
        print("No printers configured.")
        return

    # Column widths
    ip_w = 16
    name_w = 30
    model_w = 30
    status_w = 10
    updated_w = 20

    header = f"{'IP':<{ip_w}} {'Name':<{name_w}} {'Model':<{model_w}} {'Status':<{status_w}} {'Updated':<{updated_w}}"
    print(header)
    print("-" * len(header))

    for ip, info in data.items():
        name = info.get("name", ip)
        model = info.get("model", "N/A")
        status = info.get("status", "Unknown")
        ts = info.get("timestamp", "Never")
        print(f"{ip:<{ip_w}} {name:<{name_w}} {model:<{model_w}} {status:<{status_w}} {ts:<{updated_w}}")

def cmd_add(args):
    data = load_db()
    ip = args.ip.strip()
    name = args.name.strip()
    if not ip or not name:
        print("IP and Name are required.", file=sys.stderr)
        sys.exit(1)
    if ip in data:
        print(f"{ip} already exists. Updating name to '{name}'.")
    data[ip] = {
        "name": name,
        "ip": ip,
        "model": data.get(ip, {}).get("model", "N/A"),
        "serial": data.get(ip, {}).get("serial", "N/A"),
        "Toner Cartridges": data.get(ip, {}).get("Toner Cartridges", {}),
        "Drum Units": data.get(ip, {}).get("Drum Units", {}),
        "Other": data.get(ip, {}).get("Other", {}),
        "Errors": data.get(ip, {}).get("Errors", {}),
        "timestamp": data.get(ip, {}).get("timestamp", "Never"),
        "status": data.get(ip, {}).get("status", "Unknown"),
    }
    save_db(data)
    print(f"Added/updated {ip} ({name}).")

def cmd_delete(args):
    data = load_db()
    ip = args.ip.strip()
    if ip not in data:
        print(f"{ip} not found.")
        return
    data.pop(ip, None)
    save_db(data)
    print(f"Deleted {ip}.")

def _evaluate_status(printer_info: dict) -> str:
    status = "OK"
    if printer_info.get("Errors"):  # NOTE: capital E matches snmp_utils
        return "Error"
    for level_dict in [printer_info.get("Toner Cartridges", {}), printer_info.get("Drum Units", {})]:
        for val in level_dict.values():
            try:
                if isinstance(val, str) and val.endswith("%"):
                    if int(val.rstrip("%")) < 20:
                        status = "Warning"
            except:
                continue
    return status

def _merge_status(orig: dict, status: dict) -> dict:
    return {
        **orig,
        "model": status.get("Model", orig.get("model", "N/A")),
        "serial": status.get("Serial Number", orig.get("serial", "N/A")),
        "Toner Cartridges": status.get("Toner Cartridges", {}),
        "Drum Units": status.get("Drum Units", {}),
        "Other": status.get("Other", {}),
        "Errors": status.get("Errors", {}),
        "Total Pages Printed": status.get("Total Pages Printed", orig.get("Total Pages Printed", "N/A")),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

def cmd_poll(args):
    from it_tools.tonertrack.snmp_utils import get_printer_status
    data = load_db()
    ip = args.ip.strip()
    if ip not in data:
        print(f"{ip} not found in DB. Use 'add' first.", file=sys.stderr)
        sys.exit(1)
    print(f"Polling {ip} ...")
    status = get_printer_status(ip)
    merged = _merge_status(data[ip], status)
    merged["status"] = _evaluate_status(merged)
    data[ip] = merged
    save_db(data)
    print(f"Done. Status: {merged['status']}  Updated: {merged['timestamp']}")

def cmd_refresh_all(args):
    from it_tools.tonertrack.snmp_utils import get_printer_status
    data = load_db()
    if not data:
        print("No printers to refresh.")
        return
    for ip, info in list(data.items()):
        print(f"Polling {ip} ...")
        try:
            status = get_printer_status(ip)
            merged = _merge_status(info, status)
            merged["status"] = _evaluate_status(merged)
            data[ip] = merged
        except Exception as e:
            print(f"Failed {ip}: {e}", file=sys.stderr)
    save_db(data)
    print("Refresh complete.")

def cmd_show(args):
    data = load_db()
    ip = args.ip.strip()
    info = data.get(ip)
    if not info:
        print(f"{ip} not found.")
        return
    def sect(title): print(f"\n== {title} ==")
    print(f"Name: {info.get('name', ip)}")
    print(f"IP: {ip}")
    print(f"Model: {info.get('model', 'N/A')}")
    print(f"Serial: {info.get('serial', 'N/A')}")
    print(f"Status: {info.get('status', 'Unknown')}")
    print(f"Last Updated: {info.get('timestamp', 'Never')}")
    sect("Toner Cartridges")
    for k,v in (info.get("Toner Cartridges", {}) or {}).items(): print(f" - {k}: {v}")
    sect("Drum Units")
    for k,v in (info.get("Drum Units", {}) or {}).items(): print(f" - {k}: {v}")
    sect("Other")
    for k,v in (info.get("Other", {}) or {}).items(): print(f" - {k}: {v}")
    sect("Errors")
    errs = info.get("Errors", {}) or {}
    if not errs: print(" - None")
    else:
        for desc, sev in errs.items(): print(f" - [{sev}] {desc}")
    pages = info.get("Total Pages Printed", "N/A")
    print(f"\nTotal Pages Printed: {pages}")

def build_parser():
    p = argparse.ArgumentParser(prog="tonertrack", description="TonerTrack GUI/CLI")
    p.add_argument("--cli", action="store_true", help="Run in CLI mode instead of GUI.")
    sp = p.add_subparsers(dest="cmd")

    sp.add_parser("list", help="List configured printers")

    a = sp.add_parser("add", help="Add or update a printer")
    a.add_argument("--ip", required=True)
    a.add_argument("--name", required=True)

    d = sp.add_parser("delete", help="Delete a printer")
    d.add_argument("--ip", required=True)

    sh = sp.add_parser("show", help="Show details for a printer")
    sh.add_argument("--ip", required=True)

    po = sp.add_parser("poll", help="Poll one printer and save")
    po.add_argument("--ip", required=True)

    sp.add_parser("refresh-all", help="Poll all printers and save")

    return p

def run_cli(args):
    if args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "add":
        cmd_add(args)
    elif args.cmd == "delete":
        cmd_delete(args)
    elif args.cmd == "show":
        cmd_show(args)
    elif args.cmd == "poll":
        cmd_poll(args)
    elif args.cmd == "refresh-all":
        cmd_refresh_all(args)
    else:
        # Default CLI landing: show help + current printers
        print("No command provided. Showing printers:\n")
        cmd_list(args)

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.cli:
        run_cli(args)
    else:
        run_gui()
