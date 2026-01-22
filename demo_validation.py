#!/usr/bin/env python3
"""
Demo script showing the CodeValidator in action.
This demonstrates the pre-execution validation system.
"""

import sys

sys.path.insert(0, "/home/engine/project/src")

from spectral.direct_executor import CodeValidator


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_code(code, title="Code to Validate"):
    """Print code with syntax highlighting."""
    print(f"\n{title}:")
    print("-" * 70)
    for i, line in enumerate(code.strip().split("\n"), 1):
        print(f"{i:3} | {line}")
    print("-" * 70)


def validate_and_report(code, description):
    """Validate code and print detailed report."""
    print_header(description)
    print_code(code)

    validator = CodeValidator()
    result = validator.validate(code)

    print(f"\n📊 Validation Results:")
    print(f"   Status: {'✅ VALID' if result.is_valid else '❌ INVALID'}")
    print(f"   Errors: {len(result.get_error_messages())}")
    print(f"   Warnings: {len(result.get_warning_messages())}")
    print(f"   Checks: {', '.join(result.checks_performed)}")

    if result.issues:
        print(f"\n📋 Issues Detected:")
        for issue in result.issues:
            icon = "❌" if issue.severity == "error" else "⚠️"
            print(f"   {icon} {issue.message}")
            if issue.line_number:
                print(f"      → Line {issue.line_number}")
            if issue.suggestion:
                print(f"      💡 Fix: {issue.suggestion}")
    else:
        print("\n✅ No issues detected - code is ready to execute!")

    # Show auto-fix if available
    if result.has_errors():
        first_error = next((i for i in result.issues if i.severity == "error"), None)
        if first_error:
            fixed = validator.suggest_fix(code, first_error)
            if fixed:
                print(f"\n🔧 Auto-Fix Available:")
                print_code(fixed, "Fixed Code")

                # Validate fixed code
                fixed_result = validator.validate(fixed)
                if not fixed_result.has_errors():
                    print("\n✅ Fixed code validates successfully!")
                else:
                    print(
                        f"\n⚠️ Fixed code still has {len(fixed_result.get_error_messages())} error(s)"
                    )


def main():
    """Run validation demos."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "Pre-Execution Code Validation Demo" + " " * 19 + "║")
    print("╚" + "=" * 68 + "╝")

    # Demo 1: Infinite loop (catches timeout issue)
    validate_and_report(
        """
import time

def monitor_server():
    while True:
        print("Checking server...")
        time.sleep(1)

monitor_server()
""",
        "Demo 1: Infinite Loop Detection (Prevents 30s Timeout)",
    )

    # Demo 2: Socket without timeout (catches hang)
    validate_and_report(
        """
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('example.com', 80))
data = sock.recv(1024)
print(data)
""",
        "Demo 2: Missing Socket Timeout (Prevents Hang)",
    )

    # Demo 3: Blocking input (catches block)
    validate_and_report(
        """
name = input("Enter your name: ")
age = input("Enter your age: ")
print(f"Hello {name}, age {age}")
""",
        "Demo 3: Blocking Input Detection (Prevents Block)",
    )

    # Demo 4: Valid code (should pass)
    validate_and_report(
        """
import time

def process_data(items):
    results = []
    for item in items:
        result = item * 2
        results.append(result)
        time.sleep(0.01)
    return results

data = process_data([1, 2, 3, 4, 5])
print(f"Processed {len(data)} items")
""",
        "Demo 4: Valid Code (Should Pass)",
    )

    # Summary
    print_header("Summary")
    print("""
The CodeValidator system successfully:

✅ Catches infinite loops BEFORE 30-second timeout
✅ Detects missing timeouts on I/O operations
✅ Identifies blocking calls that would hang
✅ Allows valid code to execute normally
✅ Provides clear, actionable error messages
✅ Offers automatic fixes for common issues

This saves users from frustrating waits and provides immediate feedback
on code issues, dramatically improving the development experience.
""")
    print("=" * 70)


if __name__ == "__main__":
    main()
