#!/usr/bin/env python3
"""
Integration test to verify all three fixes work together end-to-end.
"""

from unittest.mock import MagicMock

from spectral.chat import ChatSession
from spectral.intent_classifier import IntentClassifier
from spectral.response_generator import ResponseGenerator


def test_full_integration():
    """Test that all components work together"""
    print("=" * 60)
    print("Integration Test: All Three Fixes Together")
    print("=" * 60)

    # Create mock orchestrator
    mock_orchestrator = MagicMock()
    mock_orchestrator.handle_command.return_value = {"status": "success", "message": "Done"}

    # Create components
    intent_classifier = IntentClassifier()
    response_generator = ResponseGenerator()

    # Create chat session
    chat_session = ChatSession(
        orchestrator=mock_orchestrator,
        intent_classifier=intent_classifier,
        response_generator=response_generator,
    )

    print("\n1. Testing conversation context...")

    # Simulate conversation
    response_generator._add_to_history("user", "hello")
    response_generator._add_to_history("assistant", "Hi! How can I help?")

    # Check history is tracked
    assert len(response_generator.conversation_history) == 2
    print("   ✅ Conversation history tracked")

    # Build prompt and verify context is included
    prompt = response_generator._build_casual_prompt("what's next?")
    assert "hello" in prompt or "Hello" in prompt
    print("   ✅ Conversation context included in prompts")

    print("\n2. Testing capability awareness...")

    # Verify capabilities are in the prompt
    assert "Code Execution" in prompt
    assert "File System Access" in prompt
    print("   ✅ Capabilities included in prompts")

    print("\n3. Testing streaming support...")

    # Verify streaming methods exist
    assert hasattr(response_generator, "generate_response_stream")
    assert hasattr(chat_session, "process_command_stream")
    print("   ✅ Streaming methods available")

    # Test that streaming yields chunks (mock LLM)
    def mock_stream():
        for word in ["Hello", " ", "world", "!"]:
            yield word

    response_generator.llm_client = MagicMock()
    response_generator.llm_client.generate_stream = MagicMock(return_value=mock_stream())

    chunks = []
    for chunk in response_generator._generate_casual_response_stream("test"):
        chunks.append(chunk)

    assert len(chunks) == 4
    assert "".join(chunks) == "Hello world!"
    print("   ✅ Streaming yields chunks correctly")

    print("\n4. Testing ChatSession integration...")

    # Test process_command_stream for casual intent
    chat_session.response_generator = response_generator

    # Mock intent classifier to return casual
    chat_session.intent_classifier.classify_intent = MagicMock(return_value="casual")

    # Mock the LLM stream
    response_generator.llm_client.generate_stream = MagicMock(
        return_value=iter(["Hi", " ", "there"])
    )

    # Process a command and collect chunks
    result_chunks = []
    for chunk in chat_session.process_command_stream("hello"):
        result_chunks.append(chunk)

    assert len(result_chunks) > 0
    print("   ✅ ChatSession streams responses correctly")

    print("\n" + "=" * 60)
    print("✅ INTEGRATION TEST PASSED!")
    print("=" * 60)
    print("\nAll three fixes work together:")
    print("  1. ✅ Conversation context is preserved and used")
    print("  2. ✅ AI is aware of its capabilities")
    print("  3. ✅ Response streaming works end-to-end")
    print()


if __name__ == "__main__":
    try:
        test_full_integration()
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
