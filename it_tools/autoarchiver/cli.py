"""AutoArchiver — CLI tool

CLI utility to bulk-enable and configure mailbox archiving for M365 / Exchange Online
users. The script is **pure-Python**, leveraging Typer for the command-line UX and
PowerShell remoting for the heavy lifting.  

MVS scope (weekend build):
    1. Read a CSV list of users (UPNs or primary SMTP addresses).
    2. Connect to Exchange Online PowerShell (assumes the module is installed).
    3. Enable archive mailboxes and apply a retention tag or policy.
    4. Log results as JSON lines for downstream ingestion.

Stretch goals are marked with TODOs.
"""

from __future__ import annotations
import csv
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Optional
import typer

APP_VERSION = "0.1.0"
app = typer.Typer(add_completion=False, help="Bulk-enable Exchange Online archive mailboxes.")
LOG = logging.getLogger("autoarchiver")

# ---------- helpers ---------------------------------------------------------

def run_ps(cmd: str, capture: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a PowerShell command and return the completed process.

    The host must already have the ExchangeOnlineManagement module installed.
    """
    full_cmd = ["pwsh", "-NoProfile", "-Command", cmd]
    LOG.debug("Executing: %s", cmd)
    return subprocess.run(full_cmd, capture_output=capture, text=True, check=False)


def ensure_eox_connection() -> None:
    """Connect to Exchange Online PowerShell if not already connected."""
    cmd = "if (-not (Get-ConnectionInformation)) { Connect-ExchangeOnline -ShowBanner:$false -UserPrincipalName 'kmadmin@beautymanufacture.com'}"
    proc = run_ps(cmd)
    if proc.returncode != 0:
        typer.echo(proc.stderr)
        typer.secho("Failed to connect to Exchange Online", fg=typer.colors.RED)
        raise typer.Exit(1)


# ---------- core logic ------------------------------------------------------

def enable_archive(upn: str, retention_policy: Optional[str], dry_run: bool = False) -> dict:
    """Enable an archive mailbox for *upn* and apply *retention_policy* (optional).

    Returns a result dict for JSONL logging.
    """
    result = {"user": upn, "archive_enabled": False, "policy": retention_policy, "error": None}
    if dry_run:
        LOG.info("[dry-run] Would enable archive for %s", upn)
        result["archive_enabled"] = "DRY_RUN"
        return result

    # PS: Enable archive mailbox
    ps_cmd = f"Enable-Mailbox -Identity '{upn}' -Archive"
    proc = run_ps(ps_cmd)
    if proc.returncode != 0:
        result["error"] = proc.stderr.strip()
        return result

    # Optional retention policy
    if retention_policy:
        ps_policy = f"Set-Mailbox -Identity '{upn}' -RetentionPolicy '{retention_policy}'"
        policy_proc = run_ps(ps_policy)
        if policy_proc.returncode != 0:
            result["error"] = policy_proc.stderr.strip()
            return result
        result["policy_applied"] = True
    result["archive_enabled"] = True
    return result


# ---------- CLI commands ----------------------------------------------------

@app.command()
def archive(
    csv_path: Path = typer.Argument(..., exists=True, readable=True, help="CSV with column 'user' containing UPNs/email addresses."),
    retention_policy: Optional[str] = typer.Option(None, "--policy", "-p", help="Existing retention policy name to apply."),
    log_file: Path = typer.Option("autoarchiver.log", "--log", help="Path to JSONL log output."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without executing PowerShell changes."),
):
    """Enable archive mailboxes for all users in *CSV_PATH*."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ensure_eox_connection()

    typer.echo(f"Processing users from {csv_path} …")
    successes, failures = 0, 0
    with csv_path.open(newline="") as fh, log_file.open("w") as lf:
        reader = csv.DictReader(fh)
        if "user" not in reader.fieldnames:
            typer.secho("CSV missing required 'user' column.", fg=typer.colors.RED)
            raise typer.Exit(1)
        for row in reader:
            upn = row["user"].strip()
            res = enable_archive(upn, retention_policy, dry_run)
            lf.write(json.dumps(res) + "\n")
            if res.get("error") or res.get("archive_enabled") is not True:
                failures += 1
                typer.secho(f"✗ {upn} — {res.get('error', 'unknown error')}", fg=typer.colors.RED)
            else:
                successes += 1
                typer.secho(f"✓ {upn}", fg=typer.colors.GREEN)
    typer.echo(f"Done. Success: {successes}, Failures: {failures}. Log → {log_file}")


@app.command()
def version() -> None:
    """Print version and exit."""
    typer.echo(APP_VERSION)


def main() -> None:  # entry-point for `python -m autoarchiver`
    app()


if __name__ == "__main__":
    from typer import run
    run(app)
