"""
Metasploit Framework knowledge base for AI-assisted penetration testing guidance.

This module provides comprehensive knowledge about Metasploit commands, payloads,
error handling, and best practices for interactive penetration testing guidance.
"""

from typing import Optional

METASPLOIT_KNOWLEDGE = {
    "commands": {
        "msfconsole": {
            "description": "Launch Metasploit framework console",
            "usage": "msfconsole",
            "output": "Shows msf> prompt when ready",
            "indicators": ["msf>", "Framework loaded"],
        },
        "search": {
            "description": "Search for exploits/payloads",
            "usage": "search <keyword>",
            "example": "search smb",
            "returns": ["Search results with IDs", "module numbers"],
            "error_codes": {
                "No results found": "Try different keyword",
                "Invalid search": "Check syntax",
            },
        },
        "use": {
            "description": "Select a module (exploit/payload/auxiliary)",
            "usage": "use <module_path>",
            "example": "use exploit/windows/smb/ms17_010_eternalblue",
            "output": "Shows module(msf exploit(module_name))> prompt",
            "indicators": ["exploit(", "payload(", "auxiliary("],
        },
        "show options": {
            "description": "Display required/optional parameters",
            "usage": "show options",
            "output": "Table with Name, Current Setting, Required, Description",
            "look_for": ["RHOST", "RPORT", "PAYLOAD", "LHOST", "LPORT"],
        },
        "set": {
            "description": "Set a parameter value",
            "usage": "set <parameter> <value>",
            "example": "set RHOST 192.168.1.100",
            "output": "Shows like: RHOST => 192.168.1.100",
            "required_sets": ["RHOST", "RPORT", "PAYLOAD", "LHOST", "LPORT"],
        },
        "run": {
            "description": "Execute the exploit/module",
            "usage": "run",
            "output": "Module execution output, success/failure messages",
            "success_indicators": [
                "[+] Meterpreter session",
                "[+] Exploit completed",
                "[*] Handler started",
            ],
        },
        "back": {
            "description": "Exit current module, return to main prompt",
            "usage": "back",
            "output": "Returns to msf> prompt",
        },
        "exit": {"description": "Exit metasploit", "usage": "exit", "output": "Closes msfconsole"},
    },
    "output_codes": {
        "[*]": "Info message",
        "[+]": "Success/positive result",
        "[-]": "Error/failure",
        "[!]": "Warning/critical issue",
        "Connection refused": "Target not responding",
        "Access denied": "Credentials failed",
        "Timeout": "Target not reachable",
    },
    "exploit_workflow": [
        "Open msfconsole (or already open)",
        "Search for appropriate exploit: search <target_type>",
        "Select exploit: use <exploit_path>",
        "Check required options: show options",
        "Set RHOST: set RHOST <target_ip>",
        "Set RPORT: set RPORT <target_port>",
        "Choose PAYLOAD if needed: set PAYLOAD <payload>",
        "Set LHOST: set LHOST <your_ip>",
        "Set LPORT: set LPORT <your_port>",
        "Run exploit: run",
        "Monitor output for success indicators: [+]",
        "Handle errors based on error codes",
    ],
    "common_payloads": {
        "windows/meterpreter/reverse_tcp": "Windows reverse shell (interactive)",
        "windows/shell_reverse_tcp": "Windows command shell",
        "linux/x86/meterpreter/reverse_tcp": "Linux reverse shell (interactive)",
        "cmd/windows/reverse_powershell": "PowerShell reverse shell",
        "windows/meterpreter_reverse_https": "HTTPS encrypted reverse shell",
    },
    "payload_guidance": {
        "meterpreter": {
            "pros": "Interactive, feature-rich, staged, can upload/download files, escalate privilege",
            "cons": "Larger, may trigger antivirus, requires specific architecture match",
            "best_for": "Full system compromise, post-exploitation, privilege escalation",
        },
        "shell": {
            "pros": "Lightweight, faster, less likely to trigger AV initially",
            "cons": "Less features, no file upload/download without tricks",
            "best_for": "Quick access, simple commands, resource-constrained targets",
        },
        "powershell": {
            "pros": "Powerful on Windows, can run scripts, built-in to modern Windows",
            "cons": "May be blocked by execution policies, easier to detect",
            "best_for": "Windows systems with PowerShell enabled, script execution",
        },
    },
    "error_handling": {
        "[*] Starting handler": "Payload handler is ready to receive connection",
        "[*] Sending stage": "Uploading second stage payload",
        "[+] Meterpreter session": "Successful shell access established",
        "[+] Handler started": "Listener is running and waiting",
        "[-] Handler failed": "Failed to establish connection/handler",
        "Connection refused": (
            "Target not listening on that port - CHECK: firewall, " "service running, correct port"
        ),
        "Module not found": "Check exploit path spelling - TRY: search for correct module name",
        "RHOST not set": "Must set target IP address with: set RHOST <ip>",
        "Exploit failed": (
            "Target patched or exploit doesn't work - TRY: different exploit, "
            "check if vulnerable"
        ),
        "Timeout": ("Target not responding - CHECK: target up, connectivity, firewall blocking"),
    },
    "post_exploitation_commands": {
        "getuid": "Show current user privileges",
        "sysinfo": "Display system information (OS, architecture, hostname)",
        "ipconfig": "Show network configuration",
        "route": "Display routing table",
        "netstat": "Show active connections",
        "ps": "List running processes",
        "cd": "Change directory",
        "pwd": "Print working directory",
        "ls": "List files",
        "cat": "Read file contents",
        "download": "Download file from target to attacker",
        "upload": "Upload file from attacker to target",
        "getsystem": "Attempt privilege escalation to SYSTEM",
        "hashdump": "Extract password hashes (requires SYSTEM privilege)",
        "persistence": "Install persistence backdoor",
        "background": "Background current session, keep running",
        "sessions": "List all active sessions",
    },
    "common_gotchas": {
        "architecture_mismatch": "x86 payload on x64 system fails - Generate correct architecture",
        "firewall_blocking": "Windows Firewall blocks outbound connection - Disable or add exception",
        "antivirus_detection": "AV quarantines payload - Try encoding or obfuscation",
        "staged_vs_stageless": "Staged = smaller initial, two-part; Stageless = larger, one-part",
        "wrong_ip": "LHOST is your attacker IP (where listener runs), not target IP",
        "port_in_use": "Port already bound - Choose different LPORT or kill process using it",
        "connection_timeout": "Listener not running, firewall blocking, or network issue",
        "payload_encoded": "Payload needs encoding for special characters/AV evasion",
        "missing_privilege": "Some commands need SYSTEM privilege (getsystem/hashdump)",
        "session_died": "Connection dropped - Re-establish or check target stability",
    },
    "privilege_escalation_tips": {
        "windows": [
            "Use getsystem in meterpreter (automatic exploitation of known vulns)",
            "Search for Windows privilege escalation exploits: search privilege_escalation windows",
            "Common vulns: UAC bypass, token impersonation, DLL injection",
            "Check: whoami /priv (current privileges before and after)",
        ],
        "linux": [
            "Search for Linux local privilege escalation: search privilege_escalation linux",
            "Check: sudo -l (what can run as sudo)",
            "Common vulns: SUID binaries, sudo misconfig, kernel exploits",
            "Try: use post/linux/gather/hashdump (if already root)",
        ],
    },
    "system_assessment_commands": {
        "windows": [
            "systeminfo",
            "wmic os get caption",
            "ipconfig /all",
            "netstat -ano",
            "tasklist /v",
            "Get-HotFix (PowerShell - list patches)",
        ],
        "linux": [
            "uname -a",
            "cat /etc/os-release",
            "ifconfig",
            "netstat -tlnp",
            "ps aux",
            "whoami",
        ],
    },
}


def get_exploit_recommendations(target_os: str, objective: str = "shell") -> list:
    """
    Get recommended exploits based on target OS and objective.

    Args:
        target_os: Target operating system (windows, linux, etc.)
        objective: Exploitation objective (shell, privilege_escalation, persistence, etc.)

    Returns:
        List of recommended exploit modules
    """
    recommendations = []

    if target_os.lower().startswith("windows"):
        if objective == "shell":
            recommendations.extend(
                [
                    "exploit/windows/smb/ms17_010_eternalblue",
                    "exploit/windows/http/apache_struts2_content_type_ognl",
                    "exploit/windows/ftp/vsftpd_234_backdoor",
                ]
            )
        elif objective == "privilege_escalation":
            recommendations.extend(
                [
                    "exploit/windows/local/bypassuac_eventvwr",
                    "exploit/windows/local/ms16_032_secondary_logon_handle_privesc",
                    "exploit/windows/local/always_install_elevated",
                ]
            )
    elif target_os.lower().startswith("linux"):
        if objective == "shell":
            recommendations.extend(
                [
                    "exploit/linux/http/distcc_exec",
                    "exploit/unix/irc/unreal_ircd_3281_backdoor",
                    "exploit/unix/samba/trans2open",
                ]
            )
        elif objective == "privilege_escalation":
            recommendations.extend(
                [
                    "exploit/linux/local/cve_2021_4034_pwnkit",
                    "exploit/linux/local/polkit_pkexec",
                    "exploit/linux/local/sudo_cve_2021_3156",
                ]
            )

    return recommendations


def get_payload_recommendations(
    target_os: str, architecture: str = "x86", objective: str = "shell"
) -> dict:
    """
    Get recommended payloads based on target OS, architecture, and objective.

    Args:
        target_os: Target operating system
        architecture: Target architecture (x86, x64)
        objective: Exploitation objective

    Returns:
        Dictionary mapping payload names to descriptions
    """
    payloads = {}

    if target_os.lower().startswith("windows"):
        if architecture.lower() in ["x64", "x86_64", "64"]:
            payloads["windows/x64/meterpreter/reverse_tcp"] = (
                "64-bit Windows Meterpreter (interactive)"
            )
            payloads["windows/x64/shell/reverse_tcp"] = "64-bit Windows shell"
            payloads["windows/x64/meterpreter/reverse_https"] = (
                "64-bit Windows HTTPS Meterpreter (encrypted)"
            )
        else:
            payloads["windows/meterpreter/reverse_tcp"] = "32-bit Windows Meterpreter (interactive)"
            payloads["windows/shell_reverse_tcp"] = "32-bit Windows shell"
            payloads["cmd/windows/reverse_powershell"] = "PowerShell reverse shell"
    elif target_os.lower().startswith("linux"):
        if architecture.lower() in ["x64", "x86_64", "64"]:
            payloads["linux/x64/meterpreter/reverse_tcp"] = "64-bit Linux Meterpreter"
            payloads["linux/x64/shell/reverse_tcp"] = "64-bit Linux shell"
        else:
            payloads["linux/x86/meterpreter/reverse_tcp"] = "32-bit Linux Meterpreter"
            payloads["linux/x86/shell/reverse_tcp"] = "32-bit Linux shell"

    return payloads


def diagnose_error(error_output: str) -> tuple[str, list[str]]:
    """
    Diagnose Metasploit error and provide fixes.

    Args:
        error_output: Error output from Metasploit

    Returns:
        Tuple of (diagnosis, list of suggested_fixes)
    """
    error_lower = error_output.lower()

    if "connection refused" in error_lower:
        diagnosis = "Target not listening on the specified port or blocking connection"
        fixes = [
            "Verify target IP is correct",
            "Check if target service is running",
            "Disable Windows Firewall: netsh advfirewall set allprofiles state off",
            "Verify target port is correct: nmap -p <port> <target_ip>",
        ]
    elif "module not found" in error_lower:
        diagnosis = "Exploit module path is incorrect or module doesn't exist"
        fixes = [
            "Search for correct module: search <keyword>",
            "Check module spelling carefully",
            "Use 'search' to find similar exploits",
            "Ensure Metasploit is up to date: msfupdate",
        ]
    elif "rhost not set" in error_lower:
        diagnosis = "Required parameter RHOST (target IP) is not configured"
        fixes = [
            "Set target IP: set RHOST <target_ip>",
            "Verify with: show options",
            "Ensure target is reachable: ping <target_ip>",
        ]
    elif "timeout" in error_lower:
        diagnosis = "Target is not responding or connection is timing out"
        fixes = [
            "Verify target is online: ping <target_ip>",
            "Check network connectivity",
            "Check if firewall is blocking connection",
            "Try different port if applicable",
        ]
    elif "access denied" in error_lower:
        diagnosis = "Authentication failed or insufficient privileges"
        fixes = [
            "Verify credentials are correct",
            "Check if account has required privileges",
            "Try privilege escalation if appropriate",
            "Use different authentication method",
        ]
    elif "exploit failed" in error_lower:
        diagnosis = "Exploit was not successful - target may be patched or not vulnerable"
        fixes = [
            "Verify target is actually vulnerable",
            "Check target OS version matches exploit requirements",
            "Try alternative exploit for the same vulnerability",
            "Research if target has patches installed",
        ]
    elif "handler failed" in error_lower:
        diagnosis = "Payload handler failed to start or accept connection"
        fixes = [
            "Check if LPORT is already in use: netstat -ano | findstr <port>",
            "Kill process using the port or choose different LPORT",
            "Verify LHOST is your actual IP address",
            "Check if antivirus is blocking the listener",
        ]
    elif "architecture" in error_lower:
        diagnosis = "Payload architecture doesn't match target architecture"
        fixes = [
            "Regenerate payload with correct architecture (x86 vs x64)",
            "Check target architecture: wmic os get osarchitecture (Windows) or uname -m (Linux)",
            "Use 'show targets' to see supported architectures",
        ]
    else:
        diagnosis = "Unknown error encountered"
        fixes = [
            "Check Metasploit logs for details",
            "Try running the module again",
            "Verify all required options are set correctly",
            "Research the specific error message online",
        ]

    return diagnosis, fixes


def get_auto_fix_command(error_type: str, error_context: dict) -> Optional[str]:
    """
    Get autonomous fix command for common errors.

    Args:
        error_type: Type of error (connection_refused, module_not_found, etc.)
        error_context: Additional context (port, ip, etc.)

    Returns:
        Command to execute for autonomous fix, or None if manual intervention required
    """
    if error_type == "firewall_blocking":
        return "netsh advfirewall set allprofiles state off"
    elif error_type == "port_in_use" and "port" in error_context:
        return f"netstat -ano | findstr :{error_context['port']}"
    elif error_type == "wrong_architecture":
        # This would require regeneration, not just a command
        return None
    elif error_type == "connection_timeout":
        return "ping " + error_context.get("target_ip", "")

    return None
