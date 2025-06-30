"""PatchPulse — cross-platform patch-compliance scanner
=====================================================
*Stage-5 IT Utilities Suite - module 2*

MVS (minimum viable scope)
-------------------------
1. **Input**: CSV of hosts with columns `host`, `os` (`windows|linux`), optional `user`, `port`.
2. **Connection**:
   • Windows   → PowerShell remoting (\u001b via `winrm` Python lib).
   • Linux     → SSH (Paramiko) and run `apt list --upgradable` or `yum check-update`.
3. **Output**: JSON Lines file noting host, OS, missing-patch count, and timestamp.
4. **CLI**: `patchpulse scan hosts.csv --out results.jsonl --prom-push http://gw:9091`.

Stretch goals (not implemented yet but outlined with TODO):
• Convert results to Prometheus metrics and push to Pushgateway.
• Grafana dashboard JSON exporter.
• GitHub Actions workflow invoking the scan nightly.
"""

from __future__ import annotations
import csv
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import typer
from dotenv import load_dotenv
from it_tools.common.env import env

try:
    import paramiko  # type: ignore
except ImportError:  # soft-dependency; warn if Linux targets are used
    paramiko = None  # pyright: ignore[reportGeneralTypeIssues]

APP_VERSION = "0.1.0"
app = typer.Typer(add_completion=False, help="PatchPulse - scan hosts for pending OS patches.")
LOG = logging.getLogger("patchpulse")

# ----------------------------- data models ----------------------------------

@dataclass
class Host:
    host: str
    os: str  # "windows" or "linux"
    user: Optional[str] = None
    port: int = 22


# ----------------------------- helpers --------------------------------------

def _run_ps_remoting(target: Host, script: str) -> str:
    """Execute *script* via PowerShell remoting (requires WinRM configured)."""
    cmd = [
        "powershell",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]
    LOG.debug("[%s] PSRemoting: %s", target.host, script)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return proc.stdout


def _run_ssh(target: Host, command: str) -> str:
    """Run *command* over SSH using paramiko (passwordless keys assumed)."""
    if paramiko is None:
        raise RuntimeError("paramiko not installed; cannot SSH to Linux hosts.")
    LOG.debug("[%s] SSH: %s", target.host, command)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(target.host, port=target.port, username=target.user or None)
    stdin, stdout, stderr = client.exec_command(command)
    out, err = stdout.read().decode(), stderr.read().decode()
    client.close()
    if err:
        raise RuntimeError(err.strip())
    return out


# ----------------------------- scanners -------------------------------------

def scan_windows(target: Host) -> dict:
    """Return dict with patch count for a Windows host."""
    # Quick+dirty: count needed updates via Get-WindowsUpdate (requires PSWindowsUpdate)
    ps_script = (
        f"Invoke-Command -ComputerName {target.host} -ScriptBlock {{ 'Import-Module PSWindowsUpdate; (Get-WindowsUpdate -IsInstalled:$false).Count' }} -Credential {env('AD_CRED')}"
    )
    try:
        output = _run_ps_remoting(target, ps_script).strip()
        pending = int(output) if output.isdigit() else None
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    return {"pending": pending}


def scan_linux(target: Host) -> dict:
    """Return dict with patch count for a Linux host (APT-based default)."""
    cmd = "apt list --upgradable 2>/dev/null | grep -v Listing | wc -l"
    try:
        output = _run_ssh(target, cmd).strip()
        pending = int(output)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    return {"pending": pending}


# ----------------------------- CLI command ----------------------------------

@app.command()
def scan(
    hosts_csv: Path = typer.Argument(..., exists=True, readable=True, help="CSV with columns: host, os (windows|linux), user?, port?"),
    out_file: Path = typer.Option("patchpulse.jsonl", "--out", help="Output JSONL path."),
    prom_push: Optional[str] = typer.Option(None, help="Prometheus Pushgateway URL (omit to skip push)."),
    dry_run: bool = typer.Option(False, help="Connect but don't modify systems (noop for scan)."),
):
    """Scan hosts listed in *HOSTS_CSV* and emit patch-status records."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    records = []
    with hosts_csv.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            host = Host(
                host=row["host"].strip(),
                os=row["os"].strip().lower(),
                user=row.get("user", None) or None,
                port=int(row.get("port", 5986)),
            )
            typer.echo(f"→ Scanning {host.host} ({host.os}) …", nl=False)
            if host.os == "windows":
                res = scan_windows(host)
            elif host.os == "linux":
                res = scan_linux(host)
            else:
                res = {"error": f"unsupported os '{host.os}'"}

            record = {
                "host": host.host,
                "os": host.os,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                **res,
            }
            records.append(record)
            if res.get("error"):
                typer.secho("  ✗" + res["error"], fg=typer.colors.RED)
            else:
                typer.secho(f"  ✓ pending updates: {res['pending']}", fg=typer.colors.GREEN)

    # ---- write JSONL
    with out_file.open("w") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    typer.echo(f"Results → {out_file} ({len(records)} hosts)")

    # ---- push metrics (TODO)
    if prom_push:
        typer.echo("Prometheus push not yet implemented (TODO)")


@app.command()
def version():
    """Print PatchPulse version."""
    typer.echo(APP_VERSION)


if __name__ == "__main__":
    from typer import run

    run(app)
