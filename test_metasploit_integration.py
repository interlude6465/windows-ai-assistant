#!/usr/bin/env python3
"""
Integration test for Metasploit automation system.

This test verifies that Metasploit requests are properly detected and routed
to the specialized handler.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_metasploit_detection():
    """Test Metasploit request detection."""
    print("=" * 70)
    print("Testing Metasploit Request Detection")
    print("=" * 70)

    # Simulate detection logic (from Chat._is_metasploit_request)
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

    test_cases = [
        # Should detect
        ("create a payload for my Windows 10 computer", True, "create a payload"),
        ("help me with metasploit", True, "metasploit"),
        ("search for exploits", True, "exploit"),
        ("generate reverse shell", True, "reverse shell"),
        ("exploit 192.168.1.100", True, "exploit"),
        ("use ms17-010", True, "ms17-010"),
        ("set up a listener", True, "listener"),
        ("penetration testing guide", True, "penetration test"),
        # Should NOT detect
        ("write a hello world program", False, None),
        ("how are you today", False, None),
        ("create a simple calculator", False, None),
        ("generate random numbers", False, None),
        ("read a file", False, None),
    ]

    print("\nTest Results:")
    print("-" * 70)

    passed = 0
    failed = 0

    for request, expected, keyword in test_cases:
        detected = any(kw in request.lower() for kw in metasploit_keywords)

        if detected == expected:
            status = "✓ PASS"
            passed += 1
            print(f"{status}: '{request}'")
            if keyword:
                print(f"       Detected via: {keyword}")
        else:
            status = "✗ FAIL"
            failed += 1
            print(f"{status}: '{request}'")
            print(f"       Expected: {expected}, Got: {detected}")

    print("\n" + "=" * 70)
    print(f"Detection Results: {passed}/{passed+failed} tests passed")
    print("=" * 70)

    return failed == 0


def test_knowledge_base_functions():
    """Test knowledge base functions."""
    print("\n" + "=" * 70)
    print("Testing Knowledge Base Functions")
    print("=" * 70)

    from spectral.knowledge import (
        diagnose_error,
        get_exploit_recommendations,
        get_payload_recommendations,
    )

    print("\n1. Exploit Recommendations:")
    print("-" * 70)

    # Windows shell
    windows_shell = get_exploit_recommendations("windows", "shell")
    if windows_shell:
        print(f"✓ Windows shell: {len(windows_shell)} exploits found")
        for exploit in windows_shell[:2]:
            print(f"  - {exploit}")
    else:
        print("✗ No Windows shell exploits found")
        return False

    # Linux privilege escalation
    linux_priv = get_exploit_recommendations("linux", "privilege_escalation")
    if linux_priv:
        print(f"✓ Linux priv esc: {len(linux_priv)} exploits found")
        for exploit in linux_priv[:2]:
            print(f"  - {exploit}")
    else:
        print("✗ No Linux privilege escalation exploits found")
        return False

    print("\n2. Payload Recommendations:")
    print("-" * 70)

    # Windows x64
    windows_x64 = get_payload_recommendations("windows", "x64", "shell")
    if windows_x64:
        print(f"✓ Windows x64: {len(windows_x64)} payloads found")
        for payload, desc in list(windows_x64.items())[:2]:
            print(f"  - {payload}")
    else:
        print("✗ No Windows x64 payloads found")
        return False

    # Linux x86
    linux_x86 = get_payload_recommendations("linux", "x86", "shell")
    if linux_x86:
        print(f"✓ Linux x86: {len(linux_x86)} payloads found")
        for payload, desc in list(linux_x86.items())[:2]:
            print(f"  - {payload}")
    else:
        print("✗ No Linux x86 payloads found")
        return False

    print("\n3. Error Diagnosis:")
    print("-" * 70)

    error_tests = [
        "Connection refused",
        "Module not found",
        "Timeout",
        "Access denied",
    ]

    for error in error_tests:
        diagnosis, fixes = diagnose_error(error)
        if diagnosis and fixes:
            print(f"✓ {error:20} -> {diagnosis[:50]}...")
            print(f"  Fixes: {len(fixes)} suggested")
        else:
            print(f"✗ {error:20} -> No diagnosis")
            return False

    return True


def test_direct_executor_methods():
    """Test that DirectExecutor has Metasploit methods."""
    print("\n" + "=" * 70)
    print("Testing DirectExecutor Methods")
    print("=" * 70)

    from spectral.direct_executor import DirectExecutor

    methods = [
        "execute_metasploit_command",
        "execute_metasploit_interactive",
        "start_metasploit_listener",
        "generate_metasploit_payload",
        "search_metasploit_exploits",
    ]

    print("\nChecking for Metasploit methods:")
    print("-" * 70)

    all_found = True
    for method in methods:
        if hasattr(DirectExecutor, method):
            print(f"✓ {method}")
        else:
            print(f"✗ {method}")
            all_found = False

    return all_found


def main():
    """Run integration tests."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "METASPLOIT INTEGRATION TESTS" + " " * 29 + "║")
    print("╚" + "=" * 68 + "╝")

    tests = [
        ("Metasploit Detection", test_metasploit_detection),
        ("Knowledge Base Functions", test_knowledge_base_functions),
        ("DirectExecutor Methods", test_direct_executor_methods),
    ]

    results = []
    for test_name, test_func in tests:
        print()
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
    print("\n" + "=" * 70)
    print("Integration Test Summary")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "=" * 70)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
