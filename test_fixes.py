#!/usr/bin/env python3
"""
Test script to verify the three critical fixes:
1. Conversation context preservation
2. Capability awareness
3. Response streaming
"""

from spectral.capability_system import get_capability_announcement
from spectral.response_generator import ResponseGenerator


def test_capability_announcement():
    """Test that capabilities are properly defined"""
    print("=" * 60)
    print("TEST 1: Capability Announcement")
    print("=" * 60)
    announcement = get_capability_announcement()
    print(announcement[:500] + "...\n")

    # Check for key capabilities
    assert "Code Execution" in announcement
    assert "File System Access" in announcement
    assert "Program Execution" in announcement
    print("✅ Capability announcement includes all key capabilities\n")


def test_conversation_history():
    """Test that conversation history is tracked"""
    print("=" * 60)
    print("TEST 2: Conversation History Tracking")
    print("=" * 60)

    rg = ResponseGenerator()

    # Simulate conversation
    rg._add_to_history("user", "Hello, what's your name?")
    rg._add_to_history("assistant", "I'm Spectral, your AI assistant!")
    rg._add_to_history("user", "Can you help me?")

    print(f"Conversation history has {len(rg.conversation_history)} messages")
    for msg in rg.conversation_history:
        print(f"  - {msg['role']}: {msg['content']}")

    assert len(rg.conversation_history) == 3
    print("\n✅ Conversation history is properly tracked\n")


def test_prompt_includes_capabilities():
    """Test that prompts include capabilities"""
    print("=" * 60)
    print("TEST 3: Prompts Include Capabilities")
    print("=" * 60)

    rg = ResponseGenerator()
    rg._add_to_history("user", "Hello")
    rg._add_to_history("assistant", "Hi there!")

    prompt = rg._build_casual_prompt("What can you do?")

    # Check that prompt includes capabilities
    assert "Code Execution" in prompt
    assert "capabilities include" in prompt or "Your capabilities include" in prompt
    print("Prompt includes capability announcement")

    # Check that prompt includes conversation history
    assert "Recent conversation" in prompt or "conversation:" in prompt
    assert "Hello" in prompt
    print("Prompt includes conversation history")

    print("\n✅ Prompts properly include capabilities and conversation history\n")


def test_streaming_exists():
    """Test that streaming method exists"""
    print("=" * 60)
    print("TEST 4: Streaming Support")
    print("=" * 60)

    rg = ResponseGenerator()

    # Check that streaming method exists
    assert hasattr(rg, "generate_response_stream")
    assert hasattr(rg, "_generate_casual_response_stream")

    print("✅ Streaming methods are available\n")


if __name__ == "__main__":
    print("\n🔧 Testing Spectral AI Fixes\n")

    try:
        test_capability_announcement()
        test_conversation_history()
        test_prompt_includes_capabilities()
        test_streaming_exists()

        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nThe three critical fixes have been successfully implemented:")
        print("1. ✅ Conversation context is now preserved")
        print("2. ✅ AI is aware of its capabilities")
        print("3. ✅ Response streaming is implemented")
        print()

    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
