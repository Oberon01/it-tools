"""TonerTrack — minimalist printer & toner inventory manager
==========================================================
Part of *IT-Tools* suite (module 3)

MVS (minimum viable scope)
-------------------------
1. **Local JSON DB** (`printers.json` by default) holds a list of printer records:
   `{ "name": "Acct-Laser-01", "ip": "10.0.0.45", "model": "HP M479fdw", "toner": "HP 414A", "location": "Accounting" }`
2. **CLI commands (Typer)**
   * `add`           - add or update a printer record
   * `list`          - tabular dump of all printers
   * `info NAME`     - pretty-print one printer's details
   * `set-toner NAME TONER` - update the toner field only
   * `search QUERY`  - fuzzy search across names, models, toners
3. No network queries (SNMP) in MVS to keep dependencies = 0; stretch goals below.

Stretch goals
-------------
• Auto-discover printers via SNMP (`pysnmp`) and pre-populate fields.
• Track toner stock count; decrement when `--replace` flag used.
• Export Prometheus metrics (printers_total, toner_count{type="HP 414A"}).
"""

from __future__ import annotations
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional
import typer
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt

APP_VERSION = "0.1.0"
DB_DEFAULT = Path("printers.json")
app = typer.Typer(add_completion=False, help="TonerTrack - printer & toner inventory CLI")
LOG = logging.getLogger("tonertrack")
console = Console()

# ----------------------------- helpers --------------------------------------

def load_db(db_path: Path) -> List[dict]:
    if not db_path.exists():
        return []
    with db_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_db(db_path: Path, data: List[dict]) -> None:
    with db_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def find_printer(data: List[dict], name: str) -> Optional[dict]:
    for rec in data:
        if rec["name"].lower() == name.lower():
            return rec
    return None


# ----------------------------- CLI commands ---------------------------------

@app.command()
def add(
    name: str = typer.Argument(..., help="Printer short name (unique key)"),
    ip: str = typer.Option(..., "--ip", prompt=True, help="IPv4/IPv6 address"),
    model: str = typer.Option(..., "--model", prompt=True, help="Printer model"),
    toner: str = typer.Option(..., "--toner", prompt=True, help="Compatible toner identifier"),
    location: str = typer.Option("", "--location", help="Room / dept location"),
    db_path: Path = typer.Option(DB_DEFAULT, "--db", help="Path to JSON inventory file"),
):
    """Add or update a printer record."""
    data = load_db(db_path)
    rec = find_printer(data, name)
    if rec:
        typer.echo(f"Updating existing printer '{name}'…")
        rec.update({"ip": ip, "model": model, "toner": toner, "location": location})
    else:
        typer.echo(f"Adding new printer '{name}'…")
        data.append({"name": name, "ip": ip, "model": model, "toner": toner, "location": location})
    save_db(db_path, data)
    typer.secho("OK", fg=typer.colors.GREEN)


@app.command()
def list(
    db_path: Path = typer.Option(DB_DEFAULT, "--db", help="Inventory JSON file"),
):
    """List all printers in a table."""
    data = load_db(db_path)
    if not data:
        typer.echo("No printers found.")
        raise typer.Exit()
    table = Table(title="TonerTrack Inventory")
    for col in ("Name", "IP", "Model", "Toner", "Location"):
        table.add_column(col)
    for rec in sorted(data, key=lambda r: r["name"]):
        table.add_row(rec["name"], rec["ip"], rec["model"], rec["toner"], rec.get("location", ""))
    console.print(table)


@app.command()
def info(
    name: str = typer.Argument(..., help="Printer name to inspect"),
    db_path: Path = typer.Option(DB_DEFAULT, "--db", help="Inventory JSON file"),
):
    """Show details for one printer."""
    rec = find_printer(load_db(db_path), name)
    if not rec:
        typer.secho(f"Printer '{name}' not found", fg=typer.colors.RED)
        raise typer.Exit(1)
    for k, v in rec.items():
        console.print(f"[bold]{k.title()}[/]: {v}")


@app.command("set-toner")
def set_toner(
    name: str = typer.Argument(..., help="Printer name"),
    toner: str = typer.Argument(..., help="New toner identifier"),
    db_path: Path = typer.Option(DB_DEFAULT, "--db", help="Inventory JSON file"),
):
    """Update toner field for *NAME*."""
    data = load_db(db_path)
    rec = find_printer(data, name)
    if not rec:
        typer.secho(f"Printer '{name}' not found", fg=typer.colors.RED)
        raise typer.Exit(1)
    rec["toner"] = toner
    save_db(db_path, data)
    typer.secho("Toner updated", fg=typer.colors.GREEN)


@app.command()
def search(
    query: str = typer.Argument(..., help="Substring to search in name, model, toner"),
    db_path: Path = typer.Option(DB_DEFAULT, "--db", help="Inventory JSON file"),
):
    """Simple fuzzy search across inventory."""
    results = []
    for rec in load_db(db_path):
        haystack = f"{rec['name']} {rec['model']} {rec['toner']}".lower()
        if query.lower() in haystack:
            results.append(rec)
    if not results:
        typer.echo("No matches.")
        raise typer.Exit()
    table = Table(title=f"Search results for '{query}'")
    for col in ("Name", "IP", "Model", "Toner", "Location"):
        table.add_column(col)
    for rec in results:
        table.add_row(rec["name"], rec["ip"], rec["model"], rec["toner"], rec.get("location", ""))
    console.print(table)


@app.command()
def version():
    """Print TonerTrack version."""
    typer.echo(APP_VERSION)


if __name__ == "__main__":
    from typer import run

    run(app)
