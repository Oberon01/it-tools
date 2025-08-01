
import json
import customtkinter as ctk
from tkinter import messagebox

DB_FILE = "printers.json"

# ---------------------- Utility Functions ----------------------

def load_db():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def find_printer(data, name):
    for rec in data:
        if rec["name"].lower() == name.lower():
            return rec
    return None

def refresh_table(table, data):
    for widget in table.winfo_children():
        widget.destroy()

    headers = ["Name", "IP", "Model", "Toner", "Location"]

    # Enable equal width stretching
    for i in range(len(headers)):
        table.grid_columnconfigure(i, weight=1)

    for i, header in enumerate(headers):
        ctk.CTkLabel(table, text=header, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=i, padx=5, pady=5, sticky="ew"
        )

    for row_idx, rec in enumerate(data, start=1):
        for col_idx, key in enumerate(["name", "ip", "model", "toner", "location"]):
            ctk.CTkLabel(table, text=rec.get(key, "")).grid(
                row=row_idx, column=col_idx, padx=5, pady=2, sticky="ew"
            )

# ------------------------ GUI Setup ------------------------

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("TonerTrack GUI")
app.geometry("900x700")

inputs = {}
fields = ["Name", "IP", "Model", "Toner", "Location"]

frame_inputs = ctk.CTkFrame(app)
frame_inputs.pack(pady=10, padx=10, fill="x")

for idx, label in enumerate(fields):
    ctk.CTkLabel(frame_inputs, text=label).grid(row=0, column=idx, padx=5)
    entry = ctk.CTkEntry(frame_inputs, width=140)
    entry.grid(row=1, column=idx, padx=5)
    inputs[label.lower()] = entry

def clear_inputs():
    for entry in inputs.values():
        entry.delete(0, 'end')

def add_or_update():
    record = {k: v.get().strip() for k, v in inputs.items()}
    if not record["name"]:
        messagebox.showerror("Error", "Printer name is required.")
        return
    data = load_db()
    existing = find_printer(data, record["name"])
    if existing:
        for k, v in record.items():
            if v:  # only update non-empty fields
                existing[k] = v
        msg = f"Updated printer '{record['name']}'."
    else:
        data.append(record)
        msg = f"Added new printer '{record['name']}'."
    save_db(data)
    refresh_table(table_frame, data)
    messagebox.showinfo("Success", msg)
    clear_inputs()

button_frame = ctk.CTkFrame(app, fg_color="transparent")
button_frame.pack(pady=10)

ctk.CTkButton(button_frame, text="Add / Update Printer", command=add_or_update).pack(side="left", padx=10)
ctk.CTkButton(button_frame, text="Clear Fields", command=clear_inputs).pack(side="left", padx=10)

# Table frame
table_frame = ctk.CTkScrollableFrame(app, width=850, height=400)
table_frame.pack(padx=10, pady=10, fill="both", expand=True)

refresh_table(table_frame, load_db())

app.mainloop()
