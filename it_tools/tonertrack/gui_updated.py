import customtkinter as ctk
import json
import tkinter as tk
from snmp_utils import get_printer_status
import threading
from datetime import datetime
import json

class TonerTrackGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TonerTrack")
        self.geometry("800x500")

        # === Left Panel ===
        self.left_frame = ctk.CTkFrame(self, width=250)
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)

        self.search_entry = ctk.CTkEntry(self.left_frame, placeholder_text="Search...")
        self.search_entry.pack(padx=10, pady=(10, 5), fill="x")
        self.search_entry.bind("<KeyRelease>", self.filter_printers)

        self.printer_listbox = tk.Listbox(self.left_frame, height=20)
        self.printer_listbox.pack(padx=10, pady=5, fill="both", expand=True)
        self.printer_listbox.bind("<<ListboxSelect>>", self.on_printer_select)


        # === Right Panel ===
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.details_label = ctk.CTkLabel(self.right_frame, text="Printer Info", font=("Arial", 18))
        self.details_label.pack(pady=(10, 5))

        self.detail_text = ctk.CTkTextbox(self.right_frame, wrap="word")
        self.detail_text.pack(padx=10, pady=10, fill="both", expand=True)

        self.refresh_button = ctk.CTkButton(self.right_frame, text="🔄 Refresh All", command=self.refresh_all_printers)
        self.refresh_button.pack(pady=10)

        # Load printer data
        self.printer_data = self.load_printers()
        self.display_printer_list()

    def load_printers(self):
        try:
            with open("printers_upgraded.json", "r") as f:
                return json.load(f)
        except Exception as e:
            print("Failed to load printer data:", e)
            return {}

    def display_printer_list(self, filtered=None):
        self.printer_listbox.delete(0, tk.END)
        for name, info in (filtered or self.printer_data).items():
            display_name = info.get("name", name)
            self.printer_listbox.insert(tk.END, display_name)

    def filter_printers(self, event=None):
        term = self.search_entry.get().lower()
        filtered = {k: v for k, v in self.printer_data.items()
                    if term in v.get('name', '').lower() or term in k.lower()}
        self.display_printer_list(filtered)

    def on_printer_select(self, event=None):
        try:
            selected_index = self.printer_listbox.curselection()
            if not selected_index:
                return
            selected_text = self.printer_listbox.get(selected_index)
            for key, val in self.printer_data.items():
                if val.get("name") == selected_text or key == selected_text:
                    self.show_printer_details(key, val)
                    break
        except Exception as e:
            print("Error selecting printer:", e)


    def show_printer_details(self, key, data): 
        self.detail_text.delete("0.0", "end")

        lines = [
            f"Name: {data.get('name', key)}",
            f"IP: {data.get('ip')}",
            f"Model: {data.get('model', 'N/A')}",
            f"Serial: {data.get('serial', 'N/A')}",
            f"Last Updated: {data.get('timestamp', 'N/A')}",
        ]

        # Toner Grouping
        toner = data.get("toner", {})
        drums = {}
        others = {}

        for k, v in toner.items():
            if "Drum" in k:
                drums[k] = v
            elif "Toner" in k:
                continue  # actual toner handled below
            else:
                others[k] = v

        toner_only = {k: v for k, v in toner.items() if "Toner" in k and "Drum" not in k}

        def section(title, group):
            if not group:
                return [f"\n{title}", "  • None found"]
            return [f"\n{title}"] + [f"  • {k}: {v}" for k, v in group.items()]

        lines += section("Toner Cartridges", toner_only)
        lines += section("Drum Units", drums)
        lines += section("Other", others)
        print(json.dumps(data.get("toner", {}), indent=2))
        self.detail_text.insert("0.0", "\n".join(lines))

    
    def refresh_all_printers(self):
        self.refresh_button.configure(state="disabled", text="🔄 Polling...")
        threading.Thread(target=self._poll_all_printers, daemon=True).start()

    def _poll_all_printers(self):
        from snmp_utils import get_printer_status  # dynamically import to avoid freezing

        updated_data = {}
        for ip, data in self.printer_data.items():
            print(f"📡 Polling {ip}...")
            try:
                status = get_printer_status(ip)
                updated_data[ip] = {
                    **data,
                    "model": status.get("Model"),
                    "serial": status.get("Serial Number"),
                    "toner": status.get("Toner Levels", {}),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            except Exception as e:
                print(f"❌ Failed to poll {ip}: {e}")
                updated_data[ip] = data  # retain old

        # Write to JSON
        with open("printers.json", "w") as f:
            json.dump(updated_data, f, indent=2)

        self.printer_data = updated_data

        # Refresh GUI (on main thread)
        self.after(100, self._post_poll_ui_refresh)

    def _post_poll_ui_refresh(self):
        self.display_printer_list()
        self.detail_text.delete("1.0", "end")
        self.refresh_button.configure(state="normal", text="🔄 Refresh All")
        print("✅ Refresh complete.")



if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = TonerTrackGUI()
    app.mainloop()
