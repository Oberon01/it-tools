# IT-Tools Suite

# 🖨 TonerTrack – Printer Monitoring Tool

**TonerTrack** is a cross-platform printer monitoring application built in Python with a modern CustomTkinter GUI.  
It provides live SNMP-based monitoring of networked printers, including **toner/drum levels**, **maintenance parts**, and **real-time error alerts**.

---

## ✨ Features
- **Three-Pane GUI Layout**
  - **Left:** Searchable list of configured printers
  - **Center:** Detailed info for the selected printer
  - **Right:** Color-coded active alerts and errors
- **Live Monitoring**
  - Auto-polls all printers every 5 minutes  
  - Manual "Refresh Now" button with spinning loader
  - Threaded SNMP polling for a responsive UI
- **Error Detection**
  - Pulls from SNMP `prtAlertTable` for real-time status (Paper Out, Jam, Cover Open, etc.)
  - Alerts are **color-coded**:
    - 🔴 **Critical**
    - 🟠 **Warning**
    - ⚪ **Info**
- **Printer Management**
  - Add and remove printers from the list
  - Stores configuration in a local JSON database (`printers_upgraded.json`)
  - Persists between sessions

---

## 🛠 Tech Stack
- **Python** – Core logic and SNMP integration  
- **CustomTkinter** – Modern themed desktop UI  
- **pysnmp** – SNMP communication with printers  
- **JSON** – Persistent printer database  

---

## 📸 Screenshots
*(Add your screenshots here — recommend showing the three-pane UI and an example alert)*

---

## 🚀 How to Run TonerTrack
1. Install dependencies:
   ```bash
   pip install customtkinter pysnmp
