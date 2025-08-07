import customtkinter as ctk
import tkinter as tk
import threading
from tkinter import messagebox, filedialog
import json
import shutil
from datetime import datetime
from it_tools.tonertrack.snmp_utils import get_printer_status
import os 
import sys

if getattr(sys, 'frozen', False):
    os.chdir(sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

def get_resource_path(filename):
    """Return absolute path to resource (handles PyInstaller temp path)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.abspath("."), filename)

def get_appdata_path(filename):
    """Return writable file path in %APPDATA%/TonerTrack/"""
    appdata_dir = os.path.join(os.getenv("APPDATA"), "TonerTrack")
    os.makedirs(appdata_dir, exist_ok=True)
    return os.path.join(appdata_dir, filename)

# Set global DB file path
DB_FILE = get_appdata_path("printers_upgraded.json")

# If DB doesn't exist, copy from bundled file
if not os.path.exists(DB_FILE):
    try:
        default_db = get_resource_path("printers_upgraded.json")
        shutil.copy(default_db, DB_FILE)
        print(f"[INIT] Copied default DB to {DB_FILE}")
    except Exception as e:
        print(f"[ERROR] Failed to copy default printer DB: {e}")

class TonerTrackMenuMixin:
    def setup_menu(self):
        menu_bar = tk.Menu(self)

        # File menu
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Import Printers", command=self.import_printer_data)
        file_menu.add_command(label="Export Printers", command=self.export_printer_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)

        # Future features menu
        tools_menu = tk.Menu(menu_bar, tearoff=0)
        tools_menu.add_command(label="Settings (Coming Soon)")
        tools_menu.add_command(label="Alert Thresholds (Coming Soon)")
        menu_bar.add_cascade(label="Tools", menu=tools_menu)

        self.config(menu=menu_bar)

    def import_printers(self):
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if file_path:
            try:
                with open(file_path, "r") as f:
                    imported = json.load(f)
                    self.printer_data.update(imported)
                    self._save_data()
                    self.display_printer_list()
                    print("✅ Printers imported.")
            except Exception as e:
                messagebox.showerror("Import Error", str(e))

    def export_printers(self):
        from tkinter import filedialog
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if file_path:
            try:
                with open(file_path, "w") as f:
                    json.dump(self.printer_data, f, indent=2)
                    print("✅ Printers exported.")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def show_about_dialog(self):
        messagebox.showinfo("About TonerTrack", "TonerTrack v1.0\nA local SNMP-based printer monitoring tool.")

class TonerTrackGUI(ctk.CTk, TonerTrackMenuMixin):
    def __init__(self):
        super().__init__()
        self.title("TonerTrack")
        self.geometry("1100x600")

        self._spinner_running = False
        self._polling_in_progress = False
        self.spinner_angle = 0

        self.load_printer_data()
        self.build_layout()
        self.display_printer_list()

        # Start auto-poll after 2 seconds, repeat every 5 minutes
        self.auto_poll_interval = 2 * 60 * 1000
        self.after(2000, self.auto_poll_cycle)

        self._prompt_initial_import()

    # ---------------- Layout ----------------
    def build_layout(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True)

        # Left pane - Printers list
        self.left_frame = ctk.CTkFrame(self.main_frame, width=220)
        self.left_frame.pack(side="left", fill="y")

        # Search
        self.search_entry = ctk.CTkEntry(self.left_frame, placeholder_text="Search printers...")
        self.search_entry.pack(padx=10, pady=(10, 5), fill="x")
        self.search_entry.bind("<KeyRelease>", lambda e: self.display_printer_list())

        # Printer listbox
        self.printer_listbox = tk.Listbox(self.left_frame, height=20)
        self.printer_listbox.pack(padx=10, pady=5, fill="both", expand=True)
        self.printer_listbox.bind("<<ListboxSelect>>", self.on_printer_select)

        # Add/Delete buttons
        self.add_button = ctk.CTkButton(self.left_frame, text="Add Printer", command=self.add_printer_popup)
        self.add_button.pack(padx=10, pady=(5, 2), fill="x")
        self.delete_button = ctk.CTkButton(self.left_frame, text="Delete Printer", command=self.delete_printer)
        self.delete_button.pack(padx=10, pady=(0, 10), fill="x")

        # Center pane - Printer details
        self.center_frame = ctk.CTkFrame(self.main_frame)
        self.center_frame.pack(side="left", fill="both", expand=True)

        self.detail_text = ctk.CTkTextbox(self.center_frame, wrap="word")
        self.detail_text.pack(padx=10, pady=10, fill="both", expand=True)

        # Right pane - Errors/alerts
        self.right_frame = ctk.CTkFrame(self.main_frame, width=280)
        self.right_frame.pack(side="right", fill="y")

        self.error_label = ctk.CTkLabel(self.right_frame, text="Active Alerts", font=ctk.CTkFont(size=16, weight="bold"))
        self.error_label.pack(pady=(10, 5))

        self.error_textbox = ctk.CTkTextbox(self.right_frame, wrap="word")
        self.error_textbox.pack(padx=10, pady=5, fill="both", expand=True)

        # Refresh button + spinner
        self.button_frame = ctk.CTkFrame(self.center_frame, fg_color="transparent")
        self.button_frame.pack(pady=(0, 10))

        self.refresh_button = ctk.CTkButton(
            self.button_frame, text="🔄 Refresh Now", command=self.refresh_all_printers
        )
        self.refresh_button.pack(side="left", padx=(0, 5))

        # Spinner canvas with safe bg color
        bg_color = self.button_frame.cget("fg_color")
        if isinstance(bg_color, tuple):
            bg_color = bg_color[1]
        if bg_color == "transparent":
            bg_color = "#2B2B2B"

        self.spinner_canvas = tk.Canvas(
            self.button_frame, width=16, height=16, highlightthickness=0, bg=bg_color
        )
        self.spinner_canvas.pack(side="left", padx=(5, 0))

        # Menu Bar
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Import Printers", command=self.import_printers)
        file_menu.add_command(label="Export Printers", command=self.export_printers)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about_dialog)
        menubar.add_cascade(label="Help", menu=help_menu)

    # ---------------- Data Handling ----------------
    def load_printer_data(self):
        try:
            with open(DB_FILE, "r") as f:
                self.printer_data = json.load(f)
        except FileNotFoundError:
            self.printer_data = {}

    def save_printer_data(self):
        with open(DB_FILE, "w") as f:
            json.dump(self.printer_data, f, indent=2)

    def _save_data(self):
        try:
            with open(DB_FILE, "w") as f:
                json.dump(self.printer_data, f, indent=2)
            print("💾 Printer data saved.")
        except Exception as e:
            print(f"❌ Failed to save data: {e}")

    def _prompt_initial_import(self):
        if not self.printer_data:  # Checks in-memory data, not file content directly
            response = messagebox.askyesno(
                "Import Printers",
                "No printers are currently configured. Would you like to import them from a file?"
            )
            if response:
                self.import_printer_data()


    # ---------------- Polling ----------------
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

    def auto_poll_cycle(self):
        self.refresh_all_printers()
        self.after(self.auto_poll_interval, self.auto_poll_cycle)

    def _poll_all_printers(self):
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
                    "Errors": status.get("Errors", {}),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            except Exception as e:
                print(f"❌ Failed to poll {ip}: {e}")
                updated_data[ip] = {**data, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

        self.printer_data = updated_data
        self.save_printer_data()
        self.after(100, self._post_poll_ui_refresh)

    def _post_poll_ui_refresh(self):
        self.display_printer_list()

        selection = self.printer_listbox.curselection()
        if selection:
            selected_name = self.printer_listbox.get(selection)
            for key, val in self.printer_data.items():
                if val.get("name") == selected_name or key == selected_name:
                    self.show_printer_details(key, val)
                    break

        self._polling_in_progress = False
        self._spinner_running = False
        self.spinner_canvas.delete("all")
        self.refresh_button.configure(state="normal")
        print("✅ Refresh complete.")

    # ---------------- UI Updates ----------------
    def display_printer_list(self):
        search_text = self.search_entry.get().lower()
        self.printer_listbox.delete(0, "end")
        for ip, info in self.printer_data.items():
            if search_text in info.get("name", "").lower():
                self.printer_listbox.insert("end", info.get("name", ip))

    def on_printer_select(self, event):
        selection = self.printer_listbox.curselection()
        if not selection:
            return
        selected_name = self.printer_listbox.get(selection)
        for key, val in self.printer_data.items():
            if val.get("name") == selected_name or key == selected_name:
                self.show_printer_details(key, val)
                break

    def show_printer_details(self, key, data):
        self.detail_text.delete("0.0", "end")
        lines = [
            f"Name: {data.get('name', key)}",
            f"IP: {data.get('ip')}",
            f"Model: {data.get('model', 'N/A')}",
            f"Serial: {data.get('serial', 'N/A')}",
            f"Last Updated: {data.get('timestamp', 'N/A')}",
            "\nToner Cartridges:"
        ]
        for k, v in data.get("Toner Cartridges", {}).items():
            lines.append(f"  • {k}: {v}")
        lines.append("\nDrum Units:")
        for k, v in data.get("Drum Units", {}).items():
            lines.append(f"  • {k}: {v}")
        lines.append("\nOther:")
        for k, v in data.get("Other", {}).items():
            lines.append(f"  • {k}: {v}")

        self.detail_text.insert("0.0", "\n".join(lines))

        # Update error panel with color coding
        self.error_textbox.configure(state="normal")
        self.error_textbox.delete("0.0", "end")
        errors = data.get("Errors", {})
        if not errors:
            self.error_textbox.insert("0.0", "No active errors.")
        else:
            for desc, severity in errors.items():
                color = {
                    "Critical": "#FF4C4C",  # Red
                    "Warning": "#FFA500",   # Orange
                    "Info": "#A0A0A0"       # Grey
                }.get(severity, "#FFFFFF")  # Default to white

                # Tag per severity
                tag_name = f"sev_{severity.lower()}"
                self.error_textbox.tag_config(tag_name, foreground=color)
                self.error_textbox.insert("end", f"{desc.upper()}\n\n", tag_name)
#               self.error_textbox.insert("end", f"{severity.upper()}: {desc.upper()}\n\n", tag_name)
                
        self.error_textbox.configure(state="disabled")

    # ---------------- Spinner ----------------
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
            outline="#00BFFF",
            width=2
        )
        self.spinner_angle = (self.spinner_angle + 10) % 360
        self.after(25, self.animate_spinner)

    # ---------------- Printer Management ----------------
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
            self.printer_data[ip] = {
                "name": name,
                "ip": ip,
                "model": "N/A",
                "serial": "N/A",
                "Toner Cartridges": {},
                "Drum Units": {},
                "Other": {},
                "Errors": {},
                "timestamp": "Never"
            }
            self.save_printer_data()
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
            self.save_printer_data()
            self.display_printer_list()
            self.detail_text.delete("0.0", "end")
            self.error_textbox.delete("0.0", "end")

def main():
    app = TonerTrackGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
