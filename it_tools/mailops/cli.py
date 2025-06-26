"""MailOps — Exchange-online admin helpers
=======================================
Part of *IT-Tools* suite (module 4)

This wraps common PowerShell snippets you already run (Block Emails, mailbox
permissions, message trace) behind a single, portable Python CLI.

MVS (minimum viable scope)
-------------------------
* **Prerequisite**: `Connect-ExchangeOnline` running in the same PowerShell
  session (or use `-Connect` flag to let MailOps open a session for you).
* **Sub-commands**
  • `block`         → add sender(s) to a Hosted Content Filter policy.
  • `grant`         → Add-MailboxPermission (full) or Add-RecipientPermission (SendAs).
  • `trace`         → Get-MessageTrace filtered by sender / recipient.
* **Logging**: JSON Lines (`mailops.log`) with timestamp + action + target.

Stretch ideas
-------------
• Bulk CSV input (multiple grants or blocks).
• Graph REST calls instead of WinRM for MFA-friendly auth.
• Prometheus counter (blocks_total, grants_total)."""

from __future__ import annotations
import json
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import typer

APP_VERSION = "0.1.1"
app = typer.Typer(add_completion=False, help="MailOps - Exchange-Online admin CLI")
LOG = logging.getLogger("mailops")

LOG_FILE = Path("mailops.log")

# ----------------------------- helpers --------------------------------------

def run_ps(cmd: str) -> str:
    """Invoke a PowerShell command and capture stdout (raise on error)."""
    proc = subprocess.run([
        "pwsh",
        "-NoProfile",
        "-Command",
        cmd,
    ], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return proc.stdout.strip()


def ensure_connection(tenant: Optional[str] = None):
    """Connect to Exchange Online if not already connected."""
    cmd = "if (-not (Get-ConnectionInformation)) { Connect-ExchangeOnline -ShowBanner:$false -UserPrincipalName <username> "  # noqa: E501
    if tenant:
        cmd += f" -Organization '{tenant}'"
    cmd += " }"
    run_ps(cmd)


def log_action(action: str, detail: dict):
    record = {"ts": datetime.now(tz=timezone.utc).isoformat(), "action": action, **detail}
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


# ----------------------------- CLI commands ---------------------------------

@app.callback()
def _common(
    connect: bool = typer.Option(False, "--connect", help="Connect to Exchange Online first."),
    tenant: Optional[str] = typer.Option(None, "--tenant", help="Tenant domain if using delegated admin"),
):
    """Shared options for all sub-commands."""
    if connect:
        typer.echo("Connecting to Exchange Online …")
        ensure_connection(tenant)


@app.command()
def block(
    sender: str = typer.Argument(..., help="Email address to block"),
    policy: str = typer.Option("Default", "--policy", help="Hosted content filter policy name"),
):
    """Add *SENDER* to the block-list of *POLICY*."""
    ps = (
        f"Import-Module ExchangeOnlineManagement; Connect-ExchangeOnline -ShowBanner:$false -UserPrincipalName <username> ; New-TenantAllowBlockListItems -ListType Sender -Block -Entries {sender} -NoExpiration -ErrorAction Stop"
        # f"Set-HostedContentFilterPolicy -Identity '{policy}' "
        # f"-BlockedSenders @('{{{sender}}}')"
    )
    run_ps(ps)
    typer.secho(f"Blocked {sender} in policy {policy}", fg=typer.colors.GREEN)
    log_action("block", {"sender": sender, "policy": policy})


@app.command()
def grant(
    mailbox: str = typer.Argument(..., help="Target mailbox (primary SMTP/UPN)"),
    user: str = typer.Argument(..., help="Grantee UPN/email"),
    access: str = typer.Option("full", "--access", "-a", help="full | sendas"),
):
    """Grant FullAccess or SendAs to *USER* on *MAILBOX*."""
    if access.lower() == "full":
        ps = f"Add-MailboxPermission -Identity '{mailbox}' -User '{user}' -AccessRights FullAccess -AutoMapping:$false"
    else:
        ps = f"Add-RecipientPermission -Identity '{mailbox}' -Trustee '{user}' -AccessRights SendAs"
    run_ps(ps)
    typer.secho(f"Granted {access} to {user} on {mailbox}", fg=typer.colors.GREEN)
    log_action("grant", {"mailbox": mailbox, "user": user, "access": access})


@app.command()
def trace(
    sender: Optional[str] = typer.Option(None, "--sender", help="Filter by sender address"),
    recipient: Optional[str] = typer.Option(None, "--recipient", help="Filter by recipient address"),
    days: int = typer.Option(9, help="How many days back"),
):
    """Run Get-MessageTrace with sender/recipient filters."""
    if not sender and not recipient:
        typer.secho("Provide --sender or --recipient", fg=typer.colors.RED)
        raise typer.Exit(1)
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%m/%d/%Y")
    end = datetime.utcnow().strftime("%m/%d/%Y")
    filters = []
    if sender:
        filters.append(f"-SenderAddress '{sender}'")
        ps = f"Import-Module ExchangeOnlineManagement; Connect-ExchangeOnline -ShowBanner:$false -UserPrincipalName <username> ; Get-MessageTraceV2 -StartDate '{start}' -EndDate '{end}' {' '.join(filters)} -ResultSize 1000 | Export-Csv $env:USERPROFILE\\exports\\SEND-{sender.split("@")[0]}_{datetime.now().strftime("%d%b")}.csv"
    if recipient:
        filters.append(f"-RecipientAddress '{recipient}'")
        ps = f"Import-Module ExchangeOnlineManagement; Connect-ExchangeOnline -ShowBanner:$false -UserPrincipalName <username> ; Get-MessageTraceV2 -StartDate '{start}' -EndDate '{end}' {' '.join(filters)} -ResultSize 1000 | Export-Csv $env:USERPROFILE\\exports\\REC-{recipient.split("@")[0]}_{datetime.now().strftime("%d%b")}.csv"
    # ps = f"Import-Module ExchangeOnlineManagement; Connect-ExchangeOnline -ShowBanner:$false -UserPrincipalName <username> ; Get-MessageTraceV2 -StartDate '{start}' -EndDate '{end}' {' '.join(filters)} -ResultSize 1000 | Export-Csv $env:USERPROFILE\\exports\\{recipient.split("@")[0]}{datetime.now()}.csv"
    output = run_ps(ps)
    typer.echo(output)
    log_action("trace", {"sender": sender, "recipient": recipient, "days": days, "result_size": 1000})


@app.command()
def version():
    """Print MailOps version."""
    typer.echo(APP_VERSION)


if __name__ == "__main__":
    from typer import run

    run(app)
