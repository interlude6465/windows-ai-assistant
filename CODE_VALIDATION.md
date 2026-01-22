# Pre-Execution Code Validation

## Overview

The CodeValidator system performs static analysis on generated code **before execution** to catch common issues that would cause timeouts, hangs, or crashes. This prevents wasting 30+ seconds waiting for execution timeouts when obvious problems can be detected immediately.

## Features

### 1. Infinite Loop Detection
- Detects `while True:` loops without break conditions or timeout logic
- Identifies recursive functions without clear base cases
- Warns about very large iteration ranges (> 1M iterations)

**Example Issue Caught:**
```python
while True:
    print("Running...")  # ❌ No break or timeout
    time.sleep(1)
```

**Auto-Fix Applied:**
```python
_iteration_count = 0
_max_iterations = 10000
while True:
    _iteration_count += 1
    if _iteration_count >= _max_iterations:
        break
    print("Running...")
    time.sleep(1)
```

### 2. Missing Timeout Detection
- Checks socket operations for timeout configuration
- Verifies thread joins have timeout parameters
- Ensures HTTP requests include timeout settings

**Example Issue Caught:**
```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('example.com', 80))  # ⚠️ No timeout set
```

**Auto-Fix Applied:**
```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(30)  # ✓ Timeout added
sock.connect(('example.com', 80))
```

### 3. Blocking Call Detection
- Detects `input()` calls that would block execution
- Identifies long `sleep()` calls (> 5 seconds)
- Warns about other blocking I/O operations

**Example Issue Caught:**
```python
name = input("Enter your name: ")  # ❌ Will block
```

**Auto-Fix Applied:**
```python
name = "test_input"  # ✓ Auto-replaced input() call
```

### 4. Structural Issues
- Detects functions with return type hints but no return statements
- Identifies unreachable code after return/break/continue
- Finds obvious undefined variable usage

### 5. Validation Output
Clear, actionable messages are shown to the user:

```
🔍 Validating code for common issues...
   ✓ Checks performed: infinite_loops, missing_timeouts, blocking_calls, missing_returns, unreachable_code, undefined_variables
   ⚠️ Warning: Socket created without explicit timeout
   ⚠️ Warning: Socket operation 'connect' may block indefinitely

❌ Validation found 1 critical issue(s):
   • Infinite loop detected: 'while True' without break or timeout

🔧 Attempting automatic fix...
   ✓ Applied fix: Add a break condition, timeout check, or iteration counter
   ↻ Re-validating fixed code...
   ✓ Code validation passed after fix
```

## Integration

The validator is automatically integrated into the execution flow:

1. **Code Generation** - AI generates code from user request
2. **Validation** - Code is analyzed for common issues
3. **Fix Attempt** - If errors found, attempt ONE automatic fix
4. **Re-validation** - Validate the fixed code
5. **Execution** - If validation passes, execute the code
6. **Abort** - If validation still fails, abort with clear message

## Validation Rules

### Errors (Block Execution)
- ❌ Infinite `while True` without break/timeout
- ❌ `input()` calls (will block)
- ❌ Socket operations without timeout configuration
- ❌ Syntax errors

### Warnings (Allow Execution)
- ⚠️ Missing timeouts on I/O operations
- ⚠️ Long sleep calls (> 5 seconds)
- ⚠️ Recursive functions without obvious base case
- ⚠️ Unreachable code
- ⚠️ Variables that may be undefined

## Performance

- Validation takes < 1 second
- Uses AST parsing for deep analysis
- Also uses regex for quick pattern detection
- Focused on common issues that cause hangs/timeouts

## Smart Fix Strategy

When validation finds errors:
1. **First Attempt** - Try automatic fix if available
2. **No Fix Available** - Abort with clear message
3. **Fix Failed** - Abort to prevent timeout/hang
4. **One Fix Only** - No retry loops, just one attempt

This prevents the system from:
- Wasting 30+ seconds on timeout
- Retrying 15 times with broken code
- Hanging on blocking operations
- Looping infinitely

## Example Usage

The validator is used automatically in DirectExecutor:

```python
# Initialize validator
validator = CodeValidator()

# Validate generated code
validation_result = validator.validate(code)

# Check for errors
if validation_result.has_errors():
    print("❌ Code has critical issues")
    for error in validation_result.get_error_messages():
        print(f"  • {error}")
    
    # Try to fix
    if attempt == 1:
        fixed_code = validator.suggest_fix(code, first_error)
        if fixed_code:
            code = fixed_code
            # Re-validate
        else:
            # Abort
            return
```

## Testing

Run the validation test suite:

```bash
python3 test_validator.py
python3 test_validation_integration.py
```

## Benefits

✅ Prevents 30-second timeouts from hidden hangs
✅ Catches infinite loops before execution
✅ Detects missing timeouts on I/O operations
✅ Blocks execution of code with `input()` calls
✅ Shows user what was validated
✅ Provides clear reasons for rejecting code
✅ Minimal fix attempt (not full retry loop)
✅ Works with all code types (sync, async, threading, sockets)

## Architecture

```
┌─────────────────┐
│  Code Generated │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   AST Parser    │  Parse code into Abstract Syntax Tree
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Validators:    │
│  • Loops        │  Run all validation checks
│  • Timeouts     │
│  • Blocking     │
│  • Structure    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Issues Found?   │
└────────┬────────┘
         │
    ┌────┴────┐
    │ No      │ Yes
    ▼         ▼
┌────────┐ ┌──────────┐
│Execute │ │Try Fix   │
└────────┘ └────┬─────┘
                │
           ┌────┴────┐
           │Fixed?   │
           └────┬────┘
                │
           ┌────┴────┐
           │Yes  │No │
           ▼     ▼
        Execute Abort
```

## Future Enhancements

Potential improvements:
- Detect memory leaks (unclosed files, sockets)
- Check for thread safety issues
- Validate async/await patterns
- Detect potential race conditions
- Check for resource exhaustion
- Integration with linters (pylint, flake8)
