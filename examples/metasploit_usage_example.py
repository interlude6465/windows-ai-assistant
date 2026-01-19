#!/usr/bin/env python3
"""
Example usage of the Metasploit Automation System.

This demonstrates how to use the Metasploit knowledge base and executor
to guide penetration testing workflows.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def example_knowledge_base():
    """Example: Using the Metasploit knowledge base."""
    print("=" * 70)
    print("Example 1: Using the Metasploit Knowledge Base")
    print("=" * 70)

    from spectral.knowledge import METASPLOIT_KNOWLEDGE

    # Display command information
    print("\n1. Command Reference:")
    print("-" * 70)
    for cmd_name, cmd_info in list(METASPLOIT_KNOWLEDGE["commands"].items())[:3]:
        print(f"\n{cmd_name.upper()}")
        print(f"  Description: {cmd_info['description']}")
        print(f"  Usage: {cmd_info['usage']}")

    # Display output codes
    print("\n\n2. Output Code Reference:")
    print("-" * 70)
    for code, meaning in METASPLOIT_KNOWLEDGE["output_codes"].items():
        print(f"  {code:15} -> {meaning}")

    # Display common payloads
    print("\n\n3. Common Payloads:")
    print("-" * 70)
    for payload, description in METASPLOIT_KNOWLEDGE["common_payloads"].items():
        print(f"  {payload:50} -> {description}")


def example_exploit_recommendations():
    """Example: Getting exploit recommendations."""
    print("\n" + "=" * 70)
    print("Example 2: Getting Exploit Recommendations")
    print("=" * 70)

    from spectral.knowledge import get_exploit_recommendations

    # Get Windows exploit recommendations
    print("\n1. Windows Shell Exploits:")
    print("-" * 70)
    exploits = get_exploit_recommendations("windows", "shell")
    for i, exploit in enumerate(exploits, 1):
        print(f"  {i}. {exploit}")

    # Get Linux privilege escalation exploits
    print("\n2. Linux Privilege Escalation Exploits:")
    print("-" * 70)
    exploits = get_exploit_recommendations("linux", "privilege_escalation")
    for i, exploit in enumerate(exploits, 1):
        print(f"  {i}. {exploit}")


def example_payload_recommendations():
    """Example: Getting payload recommendations."""
    print("\n" + "=" * 70)
    print("Example 3: Getting Payload Recommendations")
    print("=" * 70)

    from spectral.knowledge import get_payload_recommendations

    # Get Windows x64 payloads
    print("\n1. Windows x64 Payloads:")
    print("-" * 70)
    payloads = get_payload_recommendations("windows", "x64", "shell")
    for payload, description in payloads.items():
        print(f"  {payload:50}")
        print(f"    {description}")

    # Get Linux x86 payloads
    print("\n2. Linux x86 Payloads:")
    print("-" * 70)
    payloads = get_payload_recommendations("linux", "x86", "shell")
    for payload, description in payloads.items():
        print(f"  {payload:50}")
        print(f"    {description}")


def example_error_diagnosis():
    """Example: Diagnosing errors."""
    print("\n" + "=" * 70)
    print("Example 4: Error Diagnosis and Autonomous Fixing")
    print("=" * 70)

    from spectral.knowledge import diagnose_error

    # Simulate common errors
    error_outputs = [
        "Connection refused",
        "Module not found: exploit/windows/smb/invalid",
        "RHOST not set",
        "Timeout",
        "Access denied",
    ]

    for error in error_outputs:
        print(f"\nError: {error}")
        print("-" * 70)
        diagnosis, fixes = diagnose_error(error)

        print(f"Diagnosis: {diagnosis}")
        print("\nSuggested Fixes:")
        for i, fix in enumerate(fixes, 1):
            print(f"  {i}. {fix}")


def example_autonomous_fix_command():
    """Example: Getting autonomous fix commands."""
    print("\n" + "=" * 70)
    print("Example 5: Autonomous Fix Commands")
    print("=" * 70)

    from spectral.knowledge import get_auto_fix_command

    # Get fix commands for common errors
    error_contexts = [
        ("firewall_blocking", {}),
        ("port_in_use", {"port": 4444}),
        ("connection_timeout", {"target_ip": "192.168.1.100"}),
        ("wrong_architecture", {}),
    ]

    for error_type, context in error_contexts:
        print(f"\nError Type: {error_type}")
        print(f"Context: {context}")
        print("-" * 70)

        fix_cmd = get_auto_fix_command(error_type, context)

        if fix_cmd:
            print(f"Autonomous Fix Command: {fix_cmd}")
        else:
            print("Autonomous Fix: Manual intervention required")


def example_payload_guidance():
    """Example: Understanding payload types."""
    print("\n" + "=" * 70)
    print("Example 6: Payload Type Guidance")
    print("=" * 70)

    from spectral.knowledge import METASPLOIT_KNOWLEDGE

    payload_types = ["meterpreter", "shell", "powershell"]

    for payload_type in payload_types:
        print(f"\n{payload_type.upper()}")
        print("-" * 70)
        guidance = METASPLOIT_KNOWLEDGE["payload_guidance"][payload_type]
        print(f"Pros: {guidance['pros']}")
        print(f"Cons: {guidance['cons']}")
        print(f"Best For: {guidance['best_for']}")


def example_exploit_workflow():
    """Example: Understanding the exploit workflow."""
    print("\n" + "=" * 70)
    print("Example 7: Exploit Workflow Steps")
    print("=" * 70)

    from spectral.knowledge import METASPLOIT_KNOWLEDGE

    print("\nStandard Exploit Workflow:")
    print("-" * 70)
    for i, step in enumerate(METASPLOIT_KNOWLEDGE["exploit_workflow"], 1):
        print(f"  {i}. {step}")


def example_common_gotchas():
    """Example: Common gotchas and how to avoid them."""
    print("\n" + "=" * 70)
    print("Example 8: Common Gotchas")
    print("=" * 70)

    from spectral.knowledge import METASPLOIT_KNOWLEDGE

    for gotcha_name, description in METASPLOIT_KNOWLEDGE["common_gotchas"].items():
        print(f"\n{gotcha_name.replace('_', ' ').title()}")
        print("-" * 70)
        print(f"  {description}")


def example_post_exploitation():
    """Example: Post-exploitation commands."""
    print("\n" + "=" * 70)
    print("Example 9: Post-Exploitation Commands")
    print("=" * 70)

    from spectral.knowledge import METASPLOIT_KNOWLEDGE

    print("\nCommon Post-Exploitation Commands:")
    print("-" * 70)

    # Show first 8 commands
    for i, (cmd, description) in enumerate(
        list(METASPLOIT_KNOWLEDGE["post_exploitation_commands"].items())[:8], 1
    ):
        print(f"  {i:2}. {cmd:20} -> {description}")


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 10 + "METASPLOIT AUTOMATION SYSTEM - USAGE EXAMPLES" + " " * 18 + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        example_knowledge_base()
        example_exploit_recommendations()
        example_payload_recommendations()
        example_error_diagnosis()
        example_autonomous_fix_command()
        example_payload_guidance()
        example_exploit_workflow()
        example_common_gotchas()
        example_post_exploitation()

        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)

        print("\nNOTE: This is for educational purposes only.")
        print("Always obtain proper authorization before penetration testing.")
        print("=" * 70)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
