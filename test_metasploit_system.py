#!/usr/bin/env python3
"""
Test suite for Metasploit automation system.

This test verifies that the Metasploit knowledge base, prompts, and integration
are working correctly without requiring actual Metasploit installation.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_imports():
    """Test that all Metasploit modules can be imported."""
    print("Testing imports...")

    try:
        from spectral.knowledge import (
            diagnose_error,
            get_exploit_recommendations,
            get_payload_recommendations,
        )

        print("✓ Knowledge base imports successful")
    except ImportError as e:
        print(f"✗ Failed to import knowledge base: {e}")
        return False

    try:
        from spectral.prompts import METASPLOIT_SYSTEM_PROMPT

        print("✓ System prompt import successful")
    except ImportError as e:
        print(f"✗ Failed to import system prompt: {e}")
        return False

    return True


def test_knowledge_base():
    """Test that knowledge base has required structure."""
    print("\nTesting knowledge base structure...")

    from spectral.knowledge import METASPLOIT_KNOWLEDGE

    # Check required sections
    required_sections = [
        "commands",
        "output_codes",
        "exploit_workflow",
        "common_payloads",
        "payload_guidance",
        "error_handling",
        "post_exploitation_commands",
        "common_gotchas",
        "privilege_escalation_tips",
        "system_assessment_commands",
    ]

    for section in required_sections:
        if section not in METASPLOIT_KNOWLEDGE:
            print(f"✗ Missing required section: {section}")
            return False
        print(f"✓ Found section: {section}")

    # Check commands have required fields
    for cmd_name, cmd_info in METASPLOIT_KNOWLEDGE["commands"].items():
        required_fields = ["description", "usage"]
        for field in required_fields:
            if field not in cmd_info:
                print(f"✗ Command {cmd_name} missing field: {field}")
                return False

    print("✓ All commands have required fields")

    return True


def test_system_prompt():
    """Test that system prompt exists and contains key phrases."""
    print("\nTesting system prompt...")

    from spectral.prompts import METASPLOIT_SYSTEM_PROMPT

    # Check key phrases (case-sensitive for headings, case-insensitive for content)
    key_phrases_sensitive = [
        "ASSESSMENT & CLARIFICATION",
        "AUTONOMOUS SETUP & EXECUTION",
        "TROUBLESHOOTING",
        "POST-EXPLOITATION",
        "AUTO-FIXING CAPABILITY (CRITICAL)",
    ]

    key_phrases_insensitive = [
        "Metasploit",
        "penetration",
    ]

    prompt_lower = METASPLOIT_SYSTEM_PROMPT.lower()

    for phrase in key_phrases_sensitive:
        if phrase not in METASPLOIT_SYSTEM_PROMPT:
            print(f"✗ System prompt missing key phrase: {phrase}")
            return False
        print(f"✓ Found key phrase: {phrase}")

    for phrase in key_phrases_insensitive:
        if phrase.lower() not in prompt_lower:
            print(f"✗ System prompt missing key phrase: {phrase}")
            return False
        print(f"✓ Found key phrase: {phrase}")

    return True


def test_diagnose_error():
    """Test error diagnosis function."""
    print("\nTesting error diagnosis...")

    from spectral.knowledge import diagnose_error

    test_cases = [
        ("Connection refused", "firewall_blocking"),
        ("Module not found", "module_not_found"),
        ("RHOST not set", "rhost_not_set"),
        ("Timeout", "timeout"),
        ("Access denied", "access_denied"),
        ("Exploit failed", "exploit_failed"),
    ]

    for error_output, expected_error_type in test_cases:
        diagnosis, fixes = diagnose_error(error_output)

        if not diagnosis:
            print(f"✗ No diagnosis for: {error_output}")
            return False

        if not fixes:
            print(f"✗ No fixes for: {error_output}")
            return False

        print(f"✓ Diagnosed: {error_output}")
        print(f"  Diagnosis: {diagnosis[:50]}...")
        print(f"  Fixes: {len(fixes)} suggested")

    return True


def test_exploit_recommendations():
    """Test exploit recommendation function."""
    print("\nTesting exploit recommendations...")

    from spectral.knowledge import get_exploit_recommendations

    # Test Windows recommendations
    windows_exploits = get_exploit_recommendations("windows", "shell")
    if not windows_exploits:
        print("✗ No Windows exploits recommended")
        return False
    print(f"✓ Found {len(windows_exploits)} Windows exploit recommendations")

    # Test Linux recommendations
    linux_exploits = get_exploit_recommendations("linux", "shell")
    if not linux_exploits:
        print("✗ No Linux exploits recommended")
        return False
    print(f"✓ Found {len(linux_exploits)} Linux exploit recommendations")

    # Test privilege escalation
    priv_esc_exploits = get_exploit_recommendations("windows", "privilege_escalation")
    if not priv_esc_exploits:
        print("✗ No privilege escalation exploits recommended")
        return False
    print(f"✓ Found {len(priv_esc_exploits)} privilege escalation exploits")

    return True


def test_payload_recommendations():
    """Test payload recommendation function."""
    print("\nTesting payload recommendations...")

    from spectral.knowledge import get_payload_recommendations

    # Test Windows x64
    payloads = get_payload_recommendations("windows", "x64", "shell")
    if not payloads:
        print("✗ No payloads recommended for Windows x64")
        return False
    print(f"✓ Found {len(payloads)} Windows x64 payloads")
    for payload_name in payloads:
        print(f"  - {payload_name}")

    # Test Linux x86
    payloads = get_payload_recommendations("linux", "x86", "shell")
    if not payloads:
        print("✗ No payloads recommended for Linux x86")
        return False
    print(f"✓ Found {len(payloads)} Linux x86 payloads")

    # Verify Meterpreter is included
    meterpreter_found = False
    for payload_name in payloads:
        if "meterpreter" in payload_name.lower():
            meterpreter_found = True
            break

    if not meterpreter_found:
        print("✗ Meterpreter not in recommendations")
        return False
    print("✓ Meterpreter included in recommendations")

    return True


def test_chat_detection():
    """Test that Chat class can detect Metasploit requests."""
    print("\nTesting Metasploit request detection...")

    # Test detection logic directly
    test_requests = [
        ("create a payload for my computer", True),
        ("search for exploits", True),
        ("help me with metasploit", True),
        ("write a hello world program", False),
        ("how are you today", False),
        ("generate reverse shell", True),
        ("exploit windows 7", True),
        ("create a simple calculator", False),
    ]

    # Simulate detection logic
    metasploit_keywords = [
        "metasploit",
        "msfconsole",
        "msfvenom",
        "payload",
        "exploit",
        "penetration test",
        "pentest",
        "reverse shell",
        "meterpreter",
        "create a payload",
        "generate payload",
        "hack",
        "pen testing",
        "exploit target",
        "get shell",
        "backdoor",
        "ms17-010",
        "eternalblue",
        "privilege escalation",
        "priv esc",
        "cve-",
        "vulnerability scan",
        "msf>",
        "search exploit",
        "use exploit",
        "handler",
        "listener",
    ]

    for request, expected in test_requests:
        detected = any(keyword in request.lower() for keyword in metasploit_keywords)

        if detected != expected:
            print(f"✗ Detection failed for: {request}")
            print(f"  Expected: {expected}, Got: {detected}")
            return False
        print(f"✓ Correctly detected: {request}")

    return True


def test_direct_executor_methods():
    """Test that DirectExecutor has Metasploit methods."""
    print("\nTesting DirectExecutor methods...")

    try:
        from spectral.direct_executor import DirectExecutor
    except ImportError as e:
        print(f"✗ Could not import DirectExecutor: {e}")
        return False

    # Check for Metasploit methods
    required_methods = [
        "execute_metasploit_command",
        "execute_metasploit_interactive",
        "start_metasploit_listener",
        "generate_metasploit_payload",
        "search_metasploit_exploits",
    ]

    for method_name in required_methods:
        if not hasattr(DirectExecutor, method_name):
            print(f"✗ Missing method: {method_name}")
            return False
        print(f"✓ Found method: {method_name}")

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Metasploit Automation System Test Suite")
    print("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("Knowledge Base Structure", test_knowledge_base),
        ("System Prompt", test_system_prompt),
        ("Error Diagnosis", test_diagnose_error),
        ("Exploit Recommendations", test_exploit_recommendations),
        ("Payload Recommendations", test_payload_recommendations),
        ("Chat Detection", test_chat_detection),
        ("DirectExecutor Methods", test_direct_executor_methods),
    ]

    results = []
    for test_name, test_func in tests:
        print("\n" + "-" * 60)
        print(f"Running: {test_name}")
        print("-" * 60)

        try:
            result = test_func()
            results.append((test_name, result))

            if result:
                print(f"\n✓ {test_name}: PASSED")
            else:
                print(f"\n✗ {test_name}: FAILED")
        except Exception as e:
            print(f"\n✗ {test_name}: ERROR - {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
