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

            # Categorize
            if "Toner" in label:
                toner_levels[label] = percent
            elif "Drum" in label:
                drum_levels[label] = percent
            else:
                misc_levels[label] = percent

    results["Toner Cartridges"] = toner_levels
    results["Drum Units"] = drum_levels
    results["Other"] = misc_levels
    return results

def get_printer_status(ip):
    return asyncio.run(get_printer_status_async(ip))
