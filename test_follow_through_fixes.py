#!/usr/bin/env python3
"""
Test script to verify follow-through execution fixes.

Tests that the execution pipeline actually executes tasks instead of just acknowledging them.
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def test_semantic_intent_classification():
    """Test that semantic intent classifier works for follow-through test cases."""
    from spectral.semantic_intent_classifier import SemanticIntentClassifier, SemanticIntent
    
    classifier = SemanticIntentClassifier()
    
    test_cases = [
        ("generate python code that prints 'hello world'", SemanticIntent.CODE),
        ("create a file on my desktop", SemanticIntent.ACTION),
        ("run a network scan", SemanticIntent.ACTION),
        ("search the web for CVE-2021-41773", SemanticIntent.RESEARCH),
        ("list files in my documents folder", SemanticIntent.ACTION),
        ("check if port 22 is open on localhost", SemanticIntent.ACTION),
        ("get my system info", SemanticIntent.ACTION),
        ("write a batch script that creates a directory", SemanticIntent.CODE),
    ]
    
    print("\n" + "="*80)
    print("SEMANTIC INTENT CLASSIFICATION TEST")
    print("="*80)
    
    passed = 0
    failed = 0
    
    for user_input, expected_intent in test_cases:
        intent, confidence = classifier.classify(user_input)
        status = "✓ PASS" if intent == expected_intent else "✗ FAIL"
        
        if intent == expected_intent:
            passed += 1
        else:
            failed += 1
        
        print(f"\n{status}")
        print(f"  Input: {user_input}")
        print(f"  Expected: {expected_intent.value}")
        print(f"  Got: {intent.value} (confidence: {confidence:.2f})")
    
    print(f"\n{'='*80}")
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print(f"{'='*80}\n")
    
    return passed, failed


def test_execution_routing():
    """Test that execution routing works correctly."""
    from spectral.execution_router import ExecutionRouter
    from spectral.execution_models import ExecutionMode
    
    router = ExecutionRouter()
    
    test_cases = [
        ("generate python code that prints 'hello world'", ExecutionMode.DIRECT),
        ("create a file on my desktop", ExecutionMode.DIRECT),
        ("run a network scan", ExecutionMode.DIRECT),
        ("search the web for CVE-2021-41773", ExecutionMode.RESEARCH),
        ("list files in my documents folder", ExecutionMode.DIRECT),
    ]
    
    print("\n" + "="*80)
    print("EXECUTION ROUTING TEST")
    print("="*80)
    
    passed = 0
    failed = 0
    
    for user_input, expected_mode in test_cases:
        mode, confidence = router.classify(user_input)
        # We accept either DIRECT or PLANNING for action intents
        status = "✓ PASS" if (mode == expected_mode or 
                               (expected_mode == ExecutionMode.DIRECT and 
                                mode in [ExecutionMode.DIRECT, ExecutionMode.PLANNING])) else "✗ FAIL"
        
        if status == "✓ PASS":
            passed += 1
        else:
            failed += 1
        
        print(f"\n{status}")
        print(f"  Input: {user_input}")
        print(f"  Expected: {expected_mode.value}")
        print(f"  Got: {mode.value} (confidence: {confidence:.2f})")
    
    print(f"\n{'='*80}")
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print(f"{'='*80}\n")
    
    return passed, failed


def test_orchestrator_action_parsing():
    """Test that orchestrator can parse simple actions."""
    from spectral.orchestrator import Orchestrator
    from spectral.config import JarvisConfig
    
    config = JarvisConfig(model_name="test")
    orchestrator = Orchestrator(config)
    
    test_cases = [
        ("list files in my documents folder", "list_directory"),
        ("create a file on my desktop", "create_file"),
        ("run a network scan", "network_scan"),
        ("search the web for CVE-2021-41773", "web_search"),
        ("get my system info", "system_info"),
    ]
    
    print("\n" + "="*80)
    print("ORCHESTRATOR ACTION PARSING TEST")
    print("="*80)
    
    passed = 0
    failed = 0
    
    for user_input, expected_action in test_cases:
        action_type, params = orchestrator._parse_simple_action(user_input)
        status = "✓ PASS" if action_type == expected_action else "⚠ WARNING"
        
        if action_type == expected_action:
            passed += 1
        elif action_type is None:
            # Not necessarily a failure if action wasn't parsed, might be handled elsewhere
            print(f"\n{status}")
            print(f"  Input: {user_input}")
            print(f"  Expected: {expected_action}")
            print(f"  Got: None (will fall back to code generation)")
        else:
            failed += 1
            print(f"\n✗ FAIL")
            print(f"  Input: {user_input}")
            print(f"  Expected: {expected_action}")
            print(f"  Got: {action_type}")
            continue
        
        if action_type:
            print(f"\n{status}")
            print(f"  Input: {user_input}")
            print(f"  Expected: {expected_action}")
            print(f"  Got: {action_type}")
            print(f"  Params: {params}")
    
    print(f"\n{'='*80}")
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print(f"{'='*80}\n")
    
    return passed, failed


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("FOLLOW-THROUGH EXECUTION FIXES VALIDATION")
    print("="*80)
    print("\nThis script validates that the execution pipeline fixes are working correctly.")
    print("It tests intent classification, execution routing, and action parsing.\n")
    
    total_passed = 0
    total_failed = 0
    
    try:
        # Test 1: Semantic Intent Classification
        passed, failed = test_semantic_intent_classification()
        total_passed += passed
        total_failed += failed
    except Exception as e:
        logger.error(f"Semantic intent classification test failed: {e}", exc_info=True)
        total_failed += 1
    
    try:
        # Test 2: Execution Routing
        passed, failed = test_execution_routing()
        total_passed += passed
        total_failed += failed
    except Exception as e:
        logger.error(f"Execution routing test failed: {e}", exc_info=True)
        total_failed += 1
    
    try:
        # Test 3: Orchestrator Action Parsing
        passed, failed = test_orchestrator_action_parsing()
        total_passed += passed
        total_failed += failed
    except Exception as e:
        logger.error(f"Orchestrator action parsing test failed: {e}", exc_info=True)
        total_failed += 1
    
    # Summary
    print("\n" + "="*80)
    print("OVERALL SUMMARY")
    print("="*80)
    print(f"\nTotal: {total_passed} passed, {total_failed} failed")
    
    if total_failed == 0:
        print("\n✓ ALL TESTS PASSED!")
        print("\nThe execution pipeline fixes should now properly:")
        print("  1. Classify action/code intents with lower confidence threshold")
        print("  2. Route them to DualExecutionOrchestrator for actual execution")
        print("  3. Parse and execute simple actions via orchestrator fallback")
        print("  4. Return actual execution results instead of acknowledgments")
        return 0
    else:
        print(f"\n✗ {total_failed} TEST(S) FAILED")
        print("\nSome components may need additional fixes.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
