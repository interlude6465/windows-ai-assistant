#!/usr/bin/env python3
"""End-to-end test simulating real user scenarios with validation."""

import sys

sys.path.insert(0, "/home/engine/project/src")

from spectral.direct_executor import CodeValidator


def simulate_scenario(name, description, code, expected_errors):
    """Simulate a validation scenario."""
    print(f"\n{'=' * 70}")
    print(f"Scenario: {name}")
    print(f"{'=' * 70}")
    print(f"Description: {description}")
    print()

    validator = CodeValidator()
    result = validator.validate(code)

    print(f"Validation Result:")
    print(f"  Valid: {result.is_valid}")
    print(f"  Has Errors: {result.has_errors()}")
    print(f"  Checks: {', '.join(result.checks_performed)}")
    print()

    if result.issues:
        print(f"Issues Found ({len(result.issues)}):")
        for issue in result.issues:
            icon = "❌" if issue.severity == "error" else "⚠️"
            print(f"  {icon} [{issue.severity.upper()}] {issue.message}")
            if issue.line_number:
                print(f"     Line: {issue.line_number}")
            if issue.suggestion:
                print(f"     Fix: {issue.suggestion}")
        print()

    # Check if we detected expected errors
    actual_errors = result.has_errors()
    if actual_errors == expected_errors:
        print(f"✅ PASS: {'Caught' if expected_errors else 'Allowed'} as expected")
    else:
        print(f"❌ FAIL: Expected errors={expected_errors}, got errors={actual_errors}")

    # Try auto-fix if there are errors
    if result.has_errors():
        print("\n🔧 Attempting auto-fix...")
        first_error = next((i for i in result.issues if i.severity == "error"), None)
        if first_error:
            fixed = validator.suggest_fix(code, first_error)
            if fixed:
                print(f"  ✓ Fix available for: {first_error.issue_type}")
                # Validate fixed code
                fixed_result = validator.validate(fixed)
                if fixed_result.has_errors():
                    print(
                        f"  ⚠️ Fixed code still has {len(fixed_result.get_error_messages())} error(s)"
                    )
                else:
                    print(f"  ✅ Fixed code validates successfully!")
            else:
                print(f"  ❌ No auto-fix available for: {first_error.issue_type}")

    return result


def main():
    print("\n" + "=" * 70)
    print("End-to-End Validation Test Suite")
    print("Simulating real-world user scenarios")
    print("=" * 70)

    # Scenario 1: Minecraft server status checker (from requirements)
    scenario1 = simulate_scenario(
        "Minecraft Server Status Checker",
        "User wants to check if Minecraft server is online (thread pool timeout issue)",
        """
import concurrent.futures
from mcstatus import JavaServer

def check_server(address):
    while True:  # Hidden infinite loop!
        server = JavaServer.lookup(address)
        status = server.status()
        print(f"Players: {status.players.online}/{status.players.max}")

with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(check_server, "mc.example.com")
    result = future.result()  # Would hang forever
""",
        expected_errors=True,  # Should catch infinite loop
    )

    # Scenario 2: Socket ping utility (missing timeout)
    scenario2 = simulate_scenario(
        "Network Ping Utility",
        "User wants to ping a server (socket without timeout)",
        """
import socket

def ping_host(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))  # Would hang if host unreachable
    sock.close()
    return True

result = ping_host("192.168.1.1", 80)
print(f"Ping result: {result}")
""",
        expected_errors=True,  # Should catch missing timeout
    )

    # Scenario 3: Interactive calculator (input() calls)
    scenario3 = simulate_scenario(
        "Interactive Calculator",
        "User wants a calculator with input() (would block)",
        """
def calculator():
    while True:
        operation = input("Enter operation (+, -, *, /) or 'quit': ")
        if operation == 'quit':
            break
        
        num1 = float(input("Enter first number: "))
        num2 = float(input("Enter second number: "))
        
        if operation == '+':
            print(f"Result: {num1 + num2}")
        elif operation == '-':
            print(f"Result: {num1 - num2}")

calculator()
""",
        expected_errors=True,  # Should catch input() calls
    )

    # Scenario 4: Valid file processor (should pass)
    scenario4 = simulate_scenario(
        "File Processor",
        "User wants to process files (valid code)",
        """
import os
import json
from pathlib import Path

def process_json_files(directory):
    results = []
    path = Path(directory)
    
    for file_path in path.glob("*.json"):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                results.append({
                    'file': file_path.name,
                    'size': file_path.stat().st_size,
                    'data': data
                })
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    return results

if __name__ == "__main__":
    results = process_json_files("/path/to/json/files")
    print(f"Processed {len(results)} files")
""",
        expected_errors=False,  # Should pass
    )

    # Scenario 5: Web scraper (HTTP without timeout)
    scenario5 = simulate_scenario(
        "Web Scraper",
        "User wants to scrape website (HTTP without timeout)",
        """
import requests
from bs4 import BeautifulSoup

def scrape_page(url):
    response = requests.get(url)  # No timeout!
    soup = BeautifulSoup(response.text, 'html.parser')
    
    titles = []
    for title in soup.find_all('h1'):
        titles.append(title.text)
    
    return titles

results = scrape_page("https://example.com")
print(f"Found {len(results)} titles")
""",
        expected_errors=False,  # Warning only (not blocking)
    )

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(
        f"Scenario 1 (Infinite loop):    {'✅ DETECTED' if scenario1.has_errors() else '❌ MISSED'}"
    )
    print(
        f"Scenario 2 (Missing timeout):  {'✅ DETECTED' if scenario2.has_errors() else '⚠️ WARNING'}"
    )
    print(
        f"Scenario 3 (Blocking input):   {'✅ DETECTED' if scenario3.has_errors() else '❌ MISSED'}"
    )
    print(
        f"Scenario 4 (Valid code):       {'✅ PASSED' if not scenario4.has_errors() else '❌ FAILED'}"
    )
    print(
        f"Scenario 5 (HTTP no timeout):  {'⚠️ WARNING' if not scenario5.has_errors() else '❌ BLOCKED'}"
    )
    print()

    # Check overall success
    tests_passed = (
        scenario1.has_errors()  # Should catch infinite loop
        and scenario2.has_errors()  # Should catch missing timeout
        and scenario3.has_errors()  # Should catch input()
        and not scenario4.has_errors()  # Should allow valid code
        and not scenario5.has_errors()  # Should warn but allow HTTP
    )

    if tests_passed:
        print("✅ All validation tests passed!")
        print("\nValidation system successfully:")
        print("  • Prevents infinite loops")
        print("  • Detects missing timeouts")
        print("  • Blocks interactive input")
        print("  • Allows valid code")
        print("  • Provides helpful warnings")
    else:
        print("⚠️ Some tests had unexpected results")

    print("=" * 70)


if __name__ == "__main__":
    main()
