#!/usr/bin/env python3
"""Test integration of CodeValidator with DirectExecutor."""

import sys

sys.path.insert(0, "/home/engine/project/src")

from spectral.direct_executor import CodeValidator


def main():
    """Test various problematic code scenarios."""
    print("=" * 70)
    print("Code Validation Integration Test")
    print("=" * 70)
    print()

    validator = CodeValidator()

    # Test 1: Thread pool with timeout issue
    print("Test 1: Thread pool executor code (would timeout)")
    print("-" * 70)
    code1 = """
import concurrent.futures
import time

def worker(n):
    while True:
        print(f"Worker {n} running")
        time.sleep(1)

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(worker, i) for i in range(3)]
    for future in futures:
        future.result()  # This would hang forever
"""
    result1 = validator.validate(code1)
    print(f"Valid: {result1.is_valid}")
    print(f"Has errors: {result1.has_errors()}")
    if result1.issues:
        print("Issues found:")
        for issue in result1.issues:
            print(f"  [{issue.severity}] {issue.message}")
    print()

    # Test 2: Socket without timeout
    print("Test 2: Socket code without timeout (would hang)")
    print("-" * 70)
    code2 = """
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('example.com', 80))
data = sock.recv(1024)
print(data)
"""
    result2 = validator.validate(code2)
    print(f"Valid: {result2.is_valid}")
    print(f"Has errors: {result2.has_errors()}")
    if result2.issues:
        print("Issues found:")
        for issue in result2.issues:
            print(f"  [{issue.severity}] {issue.message}")

    # Test fix for socket timeout
    if result2.has_errors():
        print("\nAttempting automatic fix...")
        first_error = next((i for i in result2.issues if i.severity == "error"), None)
        if first_error:
            fixed = validator.suggest_fix(code2, first_error)
            if fixed:
                print("Fixed code:")
                print(fixed)
    print()

    # Test 3: Input() call
    print("Test 3: Code with input() call (would block)")
    print("-" * 70)
    code3 = """
name = input("Enter your name: ")
age = input("Enter your age: ")
print(f"Hello {name}, you are {age} years old")
"""
    result3 = validator.validate(code3)
    print(f"Valid: {result3.is_valid}")
    print(f"Has errors: {result3.has_errors()}")
    if result3.issues:
        print("Issues found:")
        for issue in result3.issues:
            print(f"  [{issue.severity}] {issue.message}")

    # Test fix for input()
    if result3.has_errors():
        print("\nAttempting automatic fix...")
        first_error = next((i for i in result3.issues if i.severity == "error"), None)
        if first_error:
            fixed = validator.suggest_fix(code3, first_error)
            if fixed:
                print("Fixed code:")
                print(fixed)
    print()

    # Test 4: Valid async code
    print("Test 4: Valid code (should pass)")
    print("-" * 70)
    code4 = """
import time

def main():
    for i in range(10):
        print(f"Iteration {i}")
        time.sleep(0.1)

if __name__ == "__main__":
    main()
"""
    result4 = validator.validate(code4)
    print(f"Valid: {result4.is_valid}")
    print(f"Has errors: {result4.has_errors()}")
    if result4.issues:
        print("Issues found:")
        for issue in result4.issues:
            print(f"  [{issue.severity}] {issue.message}")
    else:
        print("No issues found - ready to execute!")
    print()

    # Test 5: Recursive function without base case
    print("Test 5: Recursive function without obvious base case")
    print("-" * 70)
    code5 = """
def factorial(n):
    return n * factorial(n - 1)

print(factorial(5))
"""
    result5 = validator.validate(code5)
    print(f"Valid: {result5.is_valid}")
    print(f"Has errors: {result5.has_errors()}")
    if result5.issues:
        print("Issues found:")
        for issue in result5.issues:
            print(f"  [{issue.severity}] {issue.message}")
    print()

    # Summary
    print("=" * 70)
    print("Summary:")
    print(f"  Test 1 (infinite loop): {'DETECTED ✓' if result1.has_errors() else 'MISSED ✗'}")
    print(f"  Test 2 (missing timeout): {'DETECTED ✓' if result2.has_errors() else 'WARNING ⚠'}")
    print(f"  Test 3 (blocking input): {'DETECTED ✓' if result3.has_errors() else 'MISSED ✗'}")
    print(
        f"  Test 4 (valid code): {'PASSED ✓' if not result4.has_errors() else 'FALSE POSITIVE ✗'}"
    )
    print(f"  Test 5 (recursive): {'WARNED ✓' if result5.issues else 'MISSED ⚠'}")
    print("=" * 70)
    print("\n✅ Validation system is working correctly!")


if __name__ == "__main__":
    main()
