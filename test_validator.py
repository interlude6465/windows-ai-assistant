#!/usr/bin/env python3
"""Test script for CodeValidator functionality."""

import sys

sys.path.insert(0, "/home/engine/project/src")

from spectral.direct_executor import CodeValidator


def test_infinite_loop_detection():
    """Test detection of infinite loops."""
    print("=" * 60)
    print("TEST 1: Infinite Loop Detection")
    print("=" * 60)

    code_with_infinite_loop = """
import time

def run_forever():
    while True:
        print("Running...")
        time.sleep(1)

run_forever()
"""

    validator = CodeValidator()
    result = validator.validate(code_with_infinite_loop)

    print(f"Is valid: {result.is_valid}")
    print(f"Has errors: {result.has_errors()}")
    print(f"Checks performed: {result.checks_performed}")
    print(f"\nIssues found: {len(result.issues)}")

    for issue in result.issues:
        print(f"  - [{issue.severity}] {issue.issue_type}: {issue.message}")
        if issue.suggestion:
            print(f"    Suggestion: {issue.suggestion}")

    print("\n✓ Test 1 completed\n")


def test_missing_timeout_detection():
    """Test detection of missing timeouts."""
    print("=" * 60)
    print("TEST 2: Missing Timeout Detection")
    print("=" * 60)

    code_with_socket = """
import socket

def ping_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('example.com', 80))
    data = sock.recv(1024)
    sock.close()
    return data

ping_server()
"""

    validator = CodeValidator()
    result = validator.validate(code_with_socket)

    print(f"Is valid: {result.is_valid}")
    print(f"Has errors: {result.has_errors()}")
    print(f"Checks performed: {result.checks_performed}")
    print(f"\nIssues found: {len(result.issues)}")

    for issue in result.issues:
        print(f"  - [{issue.severity}] {issue.issue_type}: {issue.message}")
        if issue.suggestion:
            print(f"    Suggestion: {issue.suggestion}")

    print("\n✓ Test 2 completed\n")


def test_blocking_call_detection():
    """Test detection of blocking calls."""
    print("=" * 60)
    print("TEST 3: Blocking Call Detection")
    print("=" * 60)

    code_with_input = """
def get_user_name():
    name = input("Enter your name: ")
    return name

def main():
    user_name = get_user_name()
    print(f"Hello, {user_name}!")

main()
"""

    validator = CodeValidator()
    result = validator.validate(code_with_input)

    print(f"Is valid: {result.is_valid}")
    print(f"Has errors: {result.has_errors()}")
    print(f"Checks performed: {result.checks_performed}")
    print(f"\nIssues found: {len(result.issues)}")

    for issue in result.issues:
        print(f"  - [{issue.severity}] {issue.issue_type}: {issue.message}")
        if issue.suggestion:
            print(f"    Suggestion: {issue.suggestion}")

    print("\n✓ Test 3 completed\n")


def test_valid_code():
    """Test validation of valid code."""
    print("=" * 60)
    print("TEST 4: Valid Code")
    print("=" * 60)

    valid_code = """
import time

def greet(name):
    return f"Hello, {name}!"

def main():
    for i in range(10):
        message = greet(f"User {i}")
        print(message)
        time.sleep(0.1)

if __name__ == "__main__":
    main()
"""

    validator = CodeValidator()
    result = validator.validate(valid_code)

    print(f"Is valid: {result.is_valid}")
    print(f"Has errors: {result.has_errors()}")
    print(f"Checks performed: {result.checks_performed}")
    print(f"\nIssues found: {len(result.issues)}")

    for issue in result.issues:
        print(f"  - [{issue.severity}] {issue.issue_type}: {issue.message}")
        if issue.suggestion:
            print(f"    Suggestion: {issue.suggestion}")

    print("\n✓ Test 4 completed\n")


def test_fix_suggestions():
    """Test automatic fix suggestions."""
    print("=" * 60)
    print("TEST 5: Automatic Fix Suggestions")
    print("=" * 60)

    # Test infinite loop fix
    code_with_issue = """
while True:
    print("Forever")
"""

    validator = CodeValidator()
    result = validator.validate(code_with_issue)

    print("Original code has issues:")
    for issue in result.issues:
        if issue.severity == "error":
            print(f"  - {issue.message}")

            fixed_code = validator.suggest_fix(code_with_issue, issue)
            if fixed_code:
                print("\nSuggested fix:")
                print(fixed_code)
            else:
                print("\nNo automatic fix available")

    print("\n✓ Test 5 completed\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CodeValidator Test Suite")
    print("=" * 60 + "\n")

    test_infinite_loop_detection()
    test_missing_timeout_detection()
    test_blocking_call_detection()
    test_valid_code()
    test_fix_suggestions()

    print("=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
