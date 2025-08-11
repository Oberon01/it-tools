import asyncio
from pysnmp.hlapi.asyncio import *

async def snmp_get(ip, oid, community='public', timeout=2, retries=1):
    try:
        transport = await UdpTransportTarget.create(
            (ip, 161), timeout=timeout, retries=retries
        )

        errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
            SnmpEngine(),
            CommunityData(community, mpModel=0),
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )

        if errorIndication or errorStatus:
            return None

        for varBind in varBinds:
            return str(varBind[1])
    except Exception as e:
        print(f"SNMP error for {ip}: {e}")
        return None

async def snmp_walk(ip, oid_base, community='public', timeout=2, retries=1):
    """Manually walk an SNMP table for asyncio pysnmp."""
    results = {}
    try:
        transport = await UdpTransportTarget.create(
            (ip, 161), timeout=timeout, retries=retries
        )

        next_oid = ObjectIdentity(oid_base)

        while True:
            errorIndication, errorStatus, errorIndex, varBinds = await next_cmd(
                SnmpEngine(),
                CommunityData(community, mpModel=0),
                transport,
                ContextData(),
                ObjectType(next_oid),
                lexicographicMode=False
            )

            if errorIndication or errorStatus:
                break

            stop_walk = False
            for oid, val in varBinds:
                oid_str = str(oid)
                if not oid_str.startswith(oid_base):
                    stop_walk = True
                    break
                results[oid_str] = str(val)
                next_oid = ObjectIdentity(oid_str)

            if stop_walk:
                break

    except Exception as e:
        print(f"SNMP walk error for {ip}: {e}")

    return results


async def get_printer_status_async(ip):
    oids = {
        "Model": "1.3.6.1.2.1.25.3.2.1.3.1",
        "Serial Number": "1.3.6.1.2.1.43.5.1.1.17.1"
    }

    results = {}
    for label, oid in oids.items():
        value = await snmp_get(ip, oid)
        results[label] = value or "N/A"

    toner_levels = {}
    drum_levels = {}
    misc_levels = {}

    for i in range(1, 10):  # slots 1–9
        name_oid = f"1.3.6.1.2.1.43.11.1.1.6.1.{i}"
        level_oid = f"1.3.6.1.2.1.43.11.1.1.9.1.{i}"
        max_oid = f"1.3.6.1.2.1.43.11.1.1.8.1.{i}"

        name = await snmp_get(ip, name_oid)
        level = await snmp_get(ip, level_oid)
        max_val = await snmp_get(ip, max_oid)
#        print(f"[DEBUG] Slot {i}: name={name}, level={level}, max={max_val}")
        
        if name and level and max_val:
            try:
                level_int = int(level)
                max_int = int(max_val)

                if level_int == -2:
                    percent = "Unknown"
                elif max_int > 0:
                    percent = f"{round((level_int / max_int) * 100)}%"
                else:
                    percent = "N/A"
            except:
                percent = "Invalid"

            label = name.strip()

            if "toner" in label.lower():
                toner_levels[label] = percent
            elif "drum" in label.lower():
                drum_levels[label] = percent
            else:
                misc_levels[label] = percent

    # Get printer error alerts from prtAlertTable
    alerts_desc = await snmp_walk(ip, "1.3.6.1.2.1.43.18.1.1.8")  # Description
    alerts_sev = await snmp_walk(ip, "1.3.6.1.2.1.43.18.1.1.2")   # Severity

    errors = {}
    for oid, desc in alerts_desc.items():
        suffix = oid.replace("1.3.6.1.2.1.43.18.1.1.8.", "")
        severity_code = alerts_sev.get(f"1.3.6.1.2.1.43.18.1.1.2.{suffix}", "Unknown")
        severity_label = {
            "3": "Critical",
            "4": "Warning",
            "5": "Info"
        }.get(severity_code, severity_code)
        errors[desc] = severity_label

    results["Toner Cartridges"] = toner_levels
    results["Drum Units"] = drum_levels
    results["Other"] = misc_levels
    results["Errors"] = errors

    # Get total page count
    page_count_oid = "1.3.6.1.2.1.43.10.2.1.4.1.1"
    page_count = await snmp_get(ip, page_count_oid)
    results["Total Pages Printed"] = page_count or "N/A"
    
    return results

def get_printer_status(ip):
    return asyncio.run(get_printer_status_async(ip))
