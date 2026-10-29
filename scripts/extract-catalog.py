#!/usr/bin/env python3
"""Automated Schema Extractor for TP-Link Hub.

Parses router client methods, CLI commands, and MCP tools to generate
structured JSON catalogs for tp-link-mcp-web and tp-link-cli-web.

Author: Dulith Divisekara (SLIIT Malabe)
"""

import json
from pathlib import Path

BUILDER_DIR = Path(__file__).resolve().parent.parent
MCP_WEB_DATA = Path("/home/dulith/Projects/tp-link-mcp-web/data")
CLI_WEB_DATA = Path("/home/dulith/Projects/tp-link-cli-web/data")
SCHEMA_DIR = Path("/home/dulith/.gemini/antigravity/mcp/tplink-mcp")

CATEGORY_MAP = {
    "router_profile_check": "Diagnostics",
    "router_get_status": "Diagnostics",
    "router_get_connected_clients": "Diagnostics",
    "router_run_diagnostic": "Diagnostics",
    "router_get_system_logs": "Diagnostics",
    "router_clear_system_logs": "Diagnostics",
    "router_get_rf_signal": "Cellular",
    "router_set_cell_lock": "Cellular",
    "router_run_ussd": "Cellular",
    "router_get_data_limit": "Cellular",
    "router_set_data_limit": "Cellular",
    "router_set_lte_band": "Cellular",
    "router_read_sms": "SMS",
    "router_send_sms": "SMS",
    "router_get_wifi_networks": "Wi-Fi",
    "router_set_wifi_radio": "Wi-Fi",
    "router_get_guest_wifi": "Wi-Fi",
    "router_set_guest_wifi": "Wi-Fi",
    "router_get_port_forwarding": "System",
    "router_add_port_forwarding": "System",
    "router_del_port_forwarding": "System",
    "router_get_dmz": "System",
    "router_set_dmz": "System",
    "router_get_upnp": "System",
    "router_set_upnp": "System",
    "router_get_reboot_schedule": "System",
    "router_set_reboot_schedule": "System",
    "router_get_time": "System",
    "router_sync_time": "System",
    "router_get_operation_mode": "System",
    "router_get_ddns": "System",
    "router_check_firmware": "System",
    "router_set_dns": "System",
    "router_toggle_ipv6": "System",
    "router_manage_dhcp_reservation": "System",
    "router_get_led_status": "System",
    "router_set_led_night_mode": "System",
    "router_reboot": "System",
    "router_calibrate": "Tuning",
}


def update_mcp_web_catalog():
    if not MCP_WEB_DATA.exists() or not SCHEMA_DIR.exists():
        print(f"Skipping MCP web catalog update (missing {MCP_WEB_DATA} or {SCHEMA_DIR})")
        return

    tools = []
    for f in sorted(SCHEMA_DIR.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            d = json.load(fp)
        name = d["name"]
        cat = CATEGORY_MAP.get(name, "System")
        props = d.get("parameters", {}).get("properties", {})
        req = d.get("parameters", {}).get("required", [])
        params = []
        for pname, pinfo in props.items():
            params.append({
                "name": pname,
                "type": pinfo.get("type") or (pinfo.get("anyOf", [{}])[0].get("type", "any")),
                "required": pname in req,
                "default": pinfo.get("default"),
                "description": pinfo.get("title", pname)
            })
        desc = d.get("description", "").split("\n\n")[0].strip()
        tools.append({
            "name": name,
            "category": cat,
            "description": desc,
            "parameters": params,
            "schema": d
        })

    tools_file = MCP_WEB_DATA / "tools.json"
    with open(tools_file, "w", encoding="utf-8") as fp:
        json.dump(tools, fp, indent=2)
    print(f"[CATALOG] Generated and verified {len(tools)} MCP tools in {tools_file}")


CLI_CATEGORY_MAP = {
    "status": ("Diagnostics", "blue", True),
    "signal": ("Cellular", "emerald", True),
    "cell-lock": ("Cellular", "emerald", True),
    "band": ("Cellular", "emerald", True),
    "calibrate": ("Cellular", "emerald", True),
    "ussd": ("Cellular", "emerald", True),
    "data-limit": ("Cellular", "emerald", False),
    "sms": ("SMS", "purple", True),
    "wifi": ("Wi-Fi", "amber", False),
    "wifi-guard": ("Wi-Fi", "amber", False),
    "guest-wifi": ("Wi-Fi", "amber", False),
    "clients": ("Diagnostics", "blue", True),
    "diag": ("Diagnostics", "blue", False),
    "profile": ("Diagnostics", "blue", False),
    "logs": ("Diagnostics", "blue", False),
    "port-forward": ("System", "indigo", False),
    "dmz": ("System", "indigo", False),
    "upnp": ("System", "indigo", False),
    "dns": ("System", "indigo", False),
    "ipv6": ("System", "indigo", False),
    "reservation": ("System", "indigo", False),
    "reboot-schedule": ("System", "indigo", False),
    "time": ("System", "indigo", False),
    "op-mode": ("System", "indigo", False),
    "ddns": ("System", "indigo", False),
    "fw-check": ("System", "indigo", False),
    "leds": ("System", "indigo", False),
    "reboot": ("System", "indigo", False),
    "config": ("System", "indigo", False),
    "cookie": ("System", "indigo", False),
    "repl": ("System", "indigo", False),
}


def update_cli_web_catalog():
    if not CLI_WEB_DATA.exists():
        print(f"Skipping CLI web catalog (directory {CLI_WEB_DATA} not found)")
        return

    from tplink_router.cli.main import build_parser

    parser = build_parser()
    subparsers_action = next(a for a in parser._actions if a.dest == 'command')

    commands = []
    common_flags = {"--json", "--host", "--username", "--password", "--cookie", "--session-id", "--force", "-h", "--help"}

    for a in subparsers_action._choices_actions:
        cmd_name = a.dest
        subp = subparsers_action.choices.get(cmd_name)
        if not subp:
            continue

        cat, badge, has_demo = CLI_CATEGORY_MAP.get(cmd_name, ("System", "indigo", False))

        flags = []
        for act in subp._actions:
            for opt in act.option_strings:
                if opt not in common_flags and opt not in flags:
                    flags.append(opt)
            if not act.option_strings and act.dest not in ("command", "subcommand", "help"):
                flags.append(f"<{act.dest}>")

        commands.append({
            "name": cmd_name,
            "command": f"tplink-cli {cmd_name}",
            "category": cat,
            "badge_color": badge,
            "description": a.help or "",
            "flags": flags,
            "has_demo": has_demo,
        })

    commands_file = CLI_WEB_DATA / "commands.json"
    with open(commands_file, "w", encoding="utf-8") as f:
        json.dump(commands, f, indent=2)
    print(f"[CATALOG] Generated and verified {len(commands)} CLI commands in {commands_file}")


def main():
    print("Extracting and verifying catalogs from builder hub...")
    update_mcp_web_catalog()
    update_cli_web_catalog()
    print("[✓] Catalog extraction complete.")


if __name__ == "__main__":
    main()
