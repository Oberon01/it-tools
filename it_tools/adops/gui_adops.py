
import customtkinter as ctk
from tkinter import messagebox
import subprocess

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def run_ps(cmd: str) -> str:
    full = (
        "$PSStyle.OutputRendering='PlainText';"
        "Import-Module ActiveDirectory; "
        + cmd
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoLogo", "-NoProfile", "-Command", full],
            capture_output=True, text=True, check=True
        )
        return proc.stdout.strip()
    except subprocess.CalledProcessError as e:
        return e.stderr.strip()

app = ctk.CTk()

app.title("ADOps GUI")
app.geometry("900x600")

# ------------------------- User Creation -------------------------

inputs = {}
fields = [
    ("SAMAccountName", "sam"),
    ("Full Name", "name"),
    ("OU", "ou"),
    ("Title", "title"),
    ("Manager (SAM)", "manager"),
    ("Department", "dept"),
    ("Company", "comp"),
]

frame_inputs = ctk.CTkFrame(app)
frame_inputs.pack(pady=10, padx=10, fill="x")

for idx, (label, key) in enumerate(fields):
    ctk.CTkLabel(frame_inputs, text=label).grid(row=0, column=idx, padx=5)
    entry = ctk.CTkEntry(frame_inputs, width=140)
    entry.grid(row=1, column=idx, padx=5)
    inputs[key] = entry

def create_user():
    sam = inputs["sam"].get().strip()
    name = inputs["name"].get().strip()
    if not sam or not name:
        messagebox.showerror("Missing Fields", "SAM and Name are required.")
        return

    given = name.split(" ")[0]
    surname = name.split(" ")[-1]
    base_cmd = f"New-ADUser -SamAccountName '{sam}' -Name '{name}' -EmailAddress '{sam}@beautymanufacture.com' "
    base_cmd += f"-GivenName '{given}' -Surname '{surname}' -DisplayName '{name}' -UserPrincipalName '{sam}@beautymanufacture.com' "
    base_cmd += "-Enabled $true -AccountPassword (ConvertTo-SecureString -AsPlainText 'Summerful7!' -Force) "

    if inputs["ou"].get():
        base_cmd += f"-Path 'OU=B1-{inputs['ou'].get()},OU=Active,OU=BMSC1,OU=Domain Users,DC=bmsc1,DC=local' "
    if inputs["title"].get():
        base_cmd += f"-Title '{inputs['title'].get()}' "
    if inputs["manager"].get():
        base_cmd += f"-Manager '{inputs['manager'].get()}' "
    if inputs["dept"].get():
        base_cmd += f"-Department '{inputs['dept'].get()}' "
    if inputs["comp"].get():
        base_cmd += f"-Company '{inputs['comp'].get()}' "

    result = run_ps(base_cmd)
    messagebox.showinfo("Result", result)

def clear_inputs():
    for entry in inputs.values():
        entry.delete(0, 'end')

button_frame = ctk.CTkFrame(app, fg_color="transparent")
button_frame.pack(pady=10)
ctk.CTkButton(button_frame, text="Create User", command=create_user).pack(side="left", padx=10)
ctk.CTkButton(button_frame, text="Clear", command=clear_inputs).pack(side="left", padx=10)

# ------------------------- Search User -------------------------

search_frame = ctk.CTkFrame(app)
search_frame.pack(pady=20, padx=10, fill="x")

search_entry = ctk.CTkEntry(search_frame, width=300, placeholder_text="Enter SAMAccountName to search")
search_entry.pack(side="left", padx=10)
search_entry.bind("<Return>", lambda event: search_user())

search_output = ctk.CTkTextbox(app, height=180, width=800)
search_output.pack(padx=10, pady=10)

def search_user():
    import json

    sam = search_entry.get().strip()
    if not sam:
        messagebox.showerror("Missing Field", "Please enter a SAMAccountName.")
        return

    ps_script = f'''
    try {{
        $u = Get-ADUser -Identity '{sam}' -Properties Enabled,Created,PasswordLastSet,CN,Department,mail,Title,SamAccountName,UserPrincipalName,Manager
        $mgrName = if ($u.Manager) {{ (Get-ADUser -Identity $u.Manager).Name }} else {{ 'N/A' }}
        [PSCustomObject]@{{
            Name = $u.Name
            Enabled = $u.Enabled
            Created = $u.Created.toString("yyy-MM-dd HH:mm")
            PasswordLastSet = $u.PasswordLastSet.toString("yyy-MM-dd HH:mm")
            Department = $u.Department
            Email = $u.mail
            Title = $u.Title
            SAM = $u.SamAccountName
            UPN = $u.UserPrincipalName
            Manager = $mgrName
        }} | ConvertTo-Json -Compress
    }} catch {{
        '{{"error":"User not found or PowerShell error"}}'
    }}
    '''

    output = run_ps(ps_script.strip())

    try:
        user_data = json.loads(output)
        if "error" in user_data:
            formatted = f"[ERROR] {user_data['error']}"
        else:
            formatted = (
                f"Name:\t\t {user_data.get('Name', 'N/A')}\n"
                f"Enabled:\t\t {user_data.get('Enabled', 'N/A')}\n"
                f"Created:\t\t {user_data.get('Created', 'N/A')}\n"
                f"Password Set:\t\t {user_data.get('PasswordLastSet', 'N/A')}\n"
                f"Department:\t\t {user_data.get('Department', 'N/A')}\n"
                f"Email:\t\t {user_data.get('Email', 'N/A')}\n"
                f"Title:\t\t {user_data.get('Title', 'N/A')}\n"
                f"SAM:\t\t {user_data.get('SAM', 'N/A')}\n"
                f"UPN:\t\t {user_data.get('UPN', 'N/A')}\n"
                f"Manager:\t\t {user_data.get('Manager', 'N/A')}"
            )
    except json.JSONDecodeError:
        formatted = "PowerShell output could not be parsed:\n\n" + output

    search_output.delete("0.0", "end")
    search_output.insert("0.0", formatted)




ctk.CTkButton(search_frame, text="Search", command=search_user).pack(side="left", padx=10)

app.mainloop()
