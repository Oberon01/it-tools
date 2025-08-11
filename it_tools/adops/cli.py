"""ADOps — Active Directory user & group manager
==============================================
Part of *IT-Tools* suite (module 5)

MVS (minimum viable scope)
-------------------------
• **User commands**
  - `user get  <sam>`      (Get-ADUser)
  - `user new  <sam>`      (New-ADUser)  — prompts for name, OU, etc.
  - `user set  <sam>`      (Set-ADUser)  — --email, --title, --enabled/--disabled
  - `user del  <sam>`      (Remove-ADUser)

• **Group commands**
  - `group get  <name>`    (Get-ADGroup)
  - `group new  <name>`    (New-ADGroup)
  - `group del  <name>`    (Remove-ADGroup)
  - `group add-member <grp> <sam>`   (Add-ADGroupMember)
  - `group rm-member  <grp> <sam>`   (Remove-ADGroupMember)

Prerequisites
-------------
* Must run on a machine with RSAT **ActiveDirectory** PowerShell module
  (Windows desktop joined to the domain or a management server).
* Use current credentials (Kerberos). No special auth handling in MVS.

Stretch goals
-------------
• CSV bulk operations (`adops user bulk users.csv`).
• Automatically create home folders, mailbox-enable users, etc.
• Use LDAP libraries (python-ldap) for cross-platform execution.
"""

from __future__ import annotations
import logging
import subprocess
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from it_tools.common.env import env

APP_VERSION = "0.1.0"
app = typer.Typer(add_completion=False, help="ADOps - Active Directory CLI")
console = Console()

# --------------------------- helper ----------------------------------------


def run_ps(cmd: str) -> str:
    """Run *cmd* in PowerShell (requires ActiveDirectory module)."""
    full = (
        "$PSStyle.OutputRendering='PlainText';"
        "Import-Module ActiveDirectory; "
        "Clear-Host;"
        + cmd
    )
    proc = subprocess.run([
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-Command",
        full,
    ], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return proc.stdout.strip()


# --------------------------- user commands ---------------------------------

user_cli = typer.Typer(help="User management")
app.add_typer(user_cli, name="user")


@user_cli.command("get")
def user_get(
    sam: str = typer.Argument(..., help="SAMAccountName"),
    bulk: bool = typer.Option(False, "--bulk", help="Retrieve accounts in bulk")
    ):
    out = run_ps(f"Get-ADUser -Identity '{sam}' -Properties mail,title,Enabled,Manager,Office,Company | Format-List")
    print(f"\nAccount Information: {sam.upper()}\n\n{out}\n")

@user_cli.command("new")
def user_new(
    sam: str = typer.Argument(..., help="SAMAccountName"),
    name: str = typer.Option(..., "--name", prompt=True),
    ou: str = typer.Option("", "--ou", help="Target OU distinguishedName"),
    # email: str = typer.Option("", "--email", help="Email address for user"),
    title: str = typer.Option("", "--title", help="User's Job Role"),
    manager: str = typer.Option("", "--manager", help="Reporting Manager (Use SamAccountName)"),
    dept: str = typer.Option("", "--dept", help="User's Department"),
):
    parts = [f"New-ADUser -SamAccountName '{sam}' -Name '{name}' -EmailAddress '{sam}@beautymanufacture.com' -GivenName '{name.split(" ")[0]}' -Surname '{name.split(" ")[1]}' -DisplayName '{name}' -UserPrincipalName '{sam}@beautymanufacture.com' -Company 'BMSC' -Office 'BMSC' -Enabled $true -Credential {env('AD_CRED')} -AccountPassword (ConvertTo-SecureString -AsPlainText 'Summerful7!' -Force)"]
    if ou:
        parts.append(f"-Path 'OU=B1-{ou},OU=Active,OU=BMSC1,OU=Domain Users,DC=bmsc1,DC=local'")
    # if email:
        # parts.append(f"-EmailAddress '{sam}@beautymanufacture.com'")
    if title:
        parts.append(f"-Title '{title}'")
    if manager:
        parts.append(f"-Manager '{manager}'")
    if dept:
        parts.append(f"-Department '{dept}'")
    ps = " ".join(parts)
    run_ps(ps)
    console.print(f"[green]Created user {sam}")


@user_cli.command("set")
def user_set(
    sam: str = typer.Argument(...),
    email: Optional[str] = typer.Option(None, "--email"),
    title: Optional[str] = typer.Option(None, "--title"),
    dept: Optional[str] = typer.Option(None, "--dept"),
    comp: Optional[str] = typer.Option(None, "--comp"),
    enable: bool = typer.Option(False, "--enable", help="Enable account"),
    disable: bool = typer.Option(False, "--disable", help="Disable account"),
):
    parts = [f"Set-ADUser -Identity '{sam}' -Credential {env('AD_CRED')}"]
    if email:
        parts.append(f"-EmailAddress '{email}'")
    if title:
        parts.append(f"-Title '{title}'")
    if comp:
        parts.append(f"-Company '{comp}'")
    if enable:
        parts.append("-Enabled $true")
    if disable:
        parts.append("-Enabled $false")
    if dept:
        parts.append(f"-Department '{dept}'")
    run_ps(" ".join(parts))
    console.print(f"[green]Updated user {sam}")


@user_cli.command("del")
def user_del(sam: str = typer.Argument(...)):
    run_ps(f"Remove-ADUser -Identity '{sam}' -Confirm:$false")
    console.print(f"[green]Deleted user {sam}")


# --------------------------- group commands --------------------------------

group_cli = typer.Typer(help="Group management")
app.add_typer(group_cli, name="group")


@group_cli.command("get")
def group_get(name: str = typer.Argument(...)):
    out = run_ps(f"Get-ADGroup -Identity '{name}' | Format-List")
    console.print(out)


@group_cli.command("new")
def group_new(name: str = typer.Argument(...), scope: str = typer.Option("Global", "--scope", help="Global|Universal|DomainLocal")):
    run_ps(f"New-ADGroup -Name '{name}' -GroupScope {scope} -Credential {env('AD_CRED')}")
    console.print(f"[green]Created group {name}")


@group_cli.command("del")
def group_del(name: str = typer.Argument(...)):
    run_ps(f"Remove-ADGroup -Identity '{name}' -Credential {env('AD_CRED')} -Confirm:$false")
    console.print(f"[green]Deleted group {name}")


@group_cli.command("add-member")
def add_member(group: str = typer.Argument(...), sam: str = typer.Argument(...)):
    run_ps(f"Add-ADGroupMember -Identity '{group}' -Members '{sam}' -Credential {env('AD_CRED')}")
    console.print(f"[green]Added {sam} to {group}")


@group_cli.command("rm-member")
def rm_member(group: str = typer.Argument(...), sam: str = typer.Argument(...)):
    run_ps(f"Remove-ADGroupMember -Identity '{group}' -Members '{sam}' -Credential {env('AD_CRED')} -Confirm:$false")
    console.print(f"[green]Removed {sam} from {group}")


# --------------------------- misc ------------------------------------------

@app.command()
def version():
    console.print(f"ADOps v{APP_VERSION}")


if __name__ == "__main__":
    from typer import run

    run(app)
