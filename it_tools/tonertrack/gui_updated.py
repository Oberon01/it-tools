import customtkinter as ctk
import json
import tkinter as tk
from snmp_utils import get_printer_status
import threading
from datetime import datetime
import json

DB_FILE = "printers_upgraded.json"

class TonerTrackGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TonerTrack")
        self.geometry("800x500")

        # Auto-poll interval in milliseconds (5 minutes)
        self.auto_poll_interval = 5 * 60 * 1000  

        # Start the automatic polling cycle
        self.after(2000, self.auto_poll_cycle)  # wait 2 seconds before first run
        self._polling_in_progress = False

        # === Left Panel ===
        self.left_frame = ctk.CTkFrame(self, width=250)
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)

        self.search_entry = ctk.CTkEntry(self.left_frame, placeholder_text="Search...")
        self.search_entry.pack(padx=10, pady=(10, 5), fill="x")
        self.search_entry.bind("<KeyRelease>", self.filter_printers)

        self.add_button = ctk.CTkButton(self.left_frame, text="➕ Add Printer", command=self.add_printer_popup)
        self.add_button.pack(padx=10, pady=(5, 2), fill="x")

        self.delete_button = ctk.CTkButton(self.left_frame, text="🗑 Delete Printer", command=self.delete_printer)
        self.delete_button.pack(padx=10, pady=(0, 10), fill="x")


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

        # Frame for refresh button + spinner
        self.button_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.button_frame.pack(pady=5)

        # Refresh button
        self.refresh_button = ctk.CTkButton(
            self.button_frame,
            text="🔄 Refresh Now",
            command=self.refresh_all_printers
        )
        self.refresh_button.pack(side="left", padx=(0, 5))

        bg_color = self.button_frame.cget("fg_color")

        # If it's a tuple, choose the dark mode color
        if isinstance(bg_color, tuple):
            bg_color = bg_color[1]

        # If it's "transparent", fall back to a default like white or systemWindowBackground
        if bg_color == "transparent":
            try:
                bg_color = self.button_frame.master.cget("bg")  # try parent bg
            except:
                bg_color = "#2B2B2B"  # fallback to white


        # Modern arc spinner (Canvas)
        self.spinner_canvas = tk.Canvas(
            self.button_frame,
            width=16,
            height=16,
            highlightthickness=0,
            bg=bg_color
        )
        self.spinner_canvas.pack(side="left", padx=(5, 0))
        self.spinner_angle = 0
        self._spinner_running = False

        # Load printer data
        self.printer_data = self.load_printers()
        self.display_printer_list()
    
    def animate_spinner(self):
        if not self._spinner_running:
            self.spinner_canvas.delete("all")
            return

        self.spinner_canvas.delete("all")
        self.spinner_canvas.create_arc(
            2, 2, 14, 14,
            start=self.spinner_angle,
            extent=270,
            style="arc",
            outline="#00BFFF",  # modern blue
            width=2
        )
        self.spinner_angle = (self.spinner_angle + 10) % 360
        self.after(50, self.animate_spinner)


    def auto_poll_cycle(self):
        print("⏳ Auto-polling all printers...")
        self.refresh_all_printers()
        self.after(self.auto_poll_interval, self.auto_poll_cycle)  # schedule next poll


    def load_printers(self):
        try:
            with open(DB_FILE, "r") as f:
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

    def add_printer_popup(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Add Printer")
        popup.geometry("300x200")

        ctk.CTkLabel(popup, text="Printer Name:").pack(pady=5)
        name_entry = ctk.CTkEntry(popup)
        name_entry.pack(pady=5)

        ctk.CTkLabel(popup, text="Printer IP:").pack(pady=5)
        ip_entry = ctk.CTkEntry(popup)
        ip_entry.pack(pady=5)

        def save_printer():
            name = name_entry.get().strip()
            ip = ip_entry.get().strip()
            if not name or not ip:
                return

            # Add new entry to self.printer_data
            self.printer_data[ip] = {
                "name": name,
                "ip": ip,
                "model": "N/A",
                "serial": "N/A",
                "Toner Cartridges": {},
                "Drum Units": {},
                "Other": {},
                "timestamp": "Never"
            }

            # Save to JSON
            with open(DB_FILE, "w") as f:
                json.dump(self.printer_data, f, indent=2)

            # Poll just this printer
            from snmp_utils import get_printer_status
            try:
                status = get_printer_status(ip)
                self.printer_data[ip].update({
                    "model": status.get("Model"),
                    "serial": status.get("Serial Number"),
                    "Toner Cartridges": status.get("Toner Cartridges", {}),
                    "Drum Units": status.get("Drum Units", {}),
                    "Other": status.get("Other", {}),
                    "errors": status.get("Errors", {}),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                })
            except Exception as e:
                print(f"❌ Failed to poll {ip}: {e}")

            # Save updated with poll results
            with open(DB_FILE, "w") as f:
                json.dump(self.printer_data, f, indent=2)

            # Refresh list
            self.display_printer_list()
            popup.destroy()

        ctk.CTkButton(popup, text="Save", command=save_printer).pack(pady=10)

    def delete_printer(self):
        selection = self.printer_listbox.curselection()
        if not selection:
            return
        selected_name = self.printer_listbox.get(selection)
        to_delete = None
        for ip, info in self.printer_data.items():
            if info.get("name") == selected_name or ip == selected_name:
                to_delete = ip
                break

        if to_delete:
            self.printer_data.pop(to_delete, None)
            with open(DB_FILE, "w") as f:
                json.dump(self.printer_data, f, indent=2)
            self.display_printer_list()
            self.detail_text.delete("0.0", "end")


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

        # General info
        lines = [
            f"Name: {data.get('name', key)}",
            f"IP: {data.get('ip')}",
            f"Model: {data.get('model', 'N/A')}",
            f"Serial: {data.get('serial', 'N/A')}",
            f"Last Updated: {data.get('timestamp', 'N/A')}"
        ]

        # Helper to format sections
        def section(title, group):
            if not group:
                return [f"\n{title}", "  • None found"]
            return [f"\n{title}"] + [f"  • {k}: {v}" for k, v in sorted(group.items())]

        # Add grouped sections from the new JSON keys
        lines += section("Toner Cartridges", data.get("Toner Cartridges", {}))
        lines += section("Drum Units", data.get("Drum Units", {}))
        lines += section("Other", data.get("Other", {}))
        lines += section("Errors", data.get("Errors", {}))

        self.detail_text.insert("0.0", "\n".join(lines))
    
    def refresh_all_printers(self):
        if self._polling_in_progress:
            print("⚠ Restarting poll...")
            self._spinner_running = False
            self._polling_in_progress = False
        
        self._polling_in_progress = True
        self._spinner_running = True
        self.animate_spinner()
        self.refresh_button.configure(state="disabled")
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
                    "Toner Cartridges": status.get("Toner Cartridges", {}),
                    "Drum Units": status.get("Drum Units", {}),
                    "Other": status.get("Other", {}),
                    "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                }

            except Exception as e:
                print(f"❌ Failed to poll {ip}: {e}")
                updated_data[ip] = {  # retain old
                    **data,
                    "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                }

        self.printer_data = updated_data
        try:
            with open(DB_FILE, "r") as f:
                self.printer_data = json.load(f)
        except Exception as e:
            print(f"❌ Failed to reload printer data: {e}")

        self.display_printer_list()

        # If something is selected, refresh its details
        selection = self.printer_listbox.curselection()
        if selection:
            selected_name = self.printer_listbox.get(selection)
            for key, val in self.printer_data.items():
                if val.get("name") == selected_name or key == selected_name:
                    self.show_printer_details(key, val)
                    break

        # Refresh GUI (on main thread)
        self.after(100, self._post_poll_ui_refresh)

        # Write to JSON
        with open(DB_FILE, "w") as f:
            json.dump(updated_data, f, indent=2)


    def _post_poll_ui_refresh(self):
        try:
            with open(DB_FILE, "r") as f:
                self.printer_data = json.load(f)
        except Exception as e:
            print(f"❌ Failed to reload printer data: {e}")

        # Refresh list
        self.display_printer_list()

        # Auto-refresh details if a printer is selected
        selection = self.printer_listbox.curselection()
        if selection:
            selected_name = self.printer_listbox.get(selection)
            for key, val in self.printer_data.items():
                if val.get("name") == selected_name or key == selected_name:
                    self.show_printer_details(key, val)
                    break

        # Always stop spinner & re-enable button
        self._polling_in_progress = False
        self._spinner_running = False
        self.spinner_canvas.delete("all")
        self.refresh_button.configure(state="normal")

        print("✅ Refresh complete.")



if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = TonerTrackGUI()
    app.mainloop()
