"""
Unit tests for semantic intent classifier.

Tests the redesigned IntentClassifier with LLM-based semantic understanding
that handles questions, synonyms, typos, and casual phrasing.
"""

import pytest
from unittest.mock import Mock

from spectral.intent_classifier import IntentClassifier, IntentType


class TestSemanticIntentClassifier:
    """Test suite for semantic intent classification."""

    def test_classifier_accepts_llm_client(self):
        """Test that IntentClassifier accepts LLM client."""
        mock_llm = Mock()
        classifier = IntentClassifier(llm_client=mock_llm)
        assert classifier.llm_client == mock_llm

    def test_classifier_without_llm_client(self):
        """Test that IntentClassifier works without LLM client (fallback mode)."""
        classifier = IntentClassifier(llm_client=None)
        assert classifier.llm_client is None

    def test_heuristic_classification_high_confidence_imperative(self):
        """Test heuristic classification with imperative verb at start."""
        classifier = IntentClassifier(llm_client=None)
        intent, confidence = classifier.classify("create a file")
        assert intent == IntentType.ACTION
        assert confidence >= 0.8

    def test_heuristic_classification_chat_pattern(self):
        """Test heuristic classification detects chat patterns."""
        classifier = IntentClassifier(llm_client=None)
        intent, confidence = classifier.classify("how are you?")
        assert intent == IntentType.CHAT
        assert confidence >= 0.7

    def test_semantic_classification_with_llm(self):
        """Test semantic classification using LLM."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "action",
  "confidence": 0.9,
  "reasoning": "User wants to execute a command"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        # Force LLM classification by providing ambiguous input
        intent, confidence = classifier.classify("can you help me with this?")
        assert intent == IntentType.ACTION
        assert confidence == 0.9

    def test_semantic_classification_question_with_action_intent(self):
        """Test that questions with action intent are classified correctly."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "action",
  "confidence": 0.85,
  "reasoning": "Question form but user wants action performed"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        # "can you exploit this?" should be ACTION, not CHAT
        intent, confidence = classifier.classify("can you exploit this windows machine?")
        assert intent == IntentType.ACTION
        assert confidence > 0.7

    def test_semantic_classification_question_with_chat_intent(self):
        """Test that informational questions are classified as CHAT."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "chat",
  "confidence": 0.9,
  "reasoning": "User wants information, not action"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        # "how does metasploit work?" should be CHAT (informational)
        intent, confidence = classifier.classify("how does metasploit work?")
        assert intent == IntentType.CHAT
        assert confidence > 0.7

    def test_semantic_classification_with_markdown_json(self):
        """Test semantic classification handles JSON in markdown code blocks."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """```json
{
  "intent": "action",
  "confidence": 0.8,
  "reasoning": "Action request"
}
```"""
        classifier = IntentClassifier(llm_client=mock_llm)

        intent, confidence = classifier.classify("what ports are open on target?")
        assert intent == IntentType.ACTION
        assert confidence == 0.8

    def test_semantic_classification_fallback_on_error(self):
        """Test that classification falls back to heuristics on LLM error."""
        mock_llm = Mock()
        mock_llm.generate.side_effect = Exception("LLM connection failed")
        classifier = IntentClassifier(llm_client=mock_llm)

        # Should fall back to heuristics
        intent, confidence = classifier.classify("open file")
        # Heuristic should detect "open" verb
        assert intent == IntentType.ACTION

    def test_semantic_classification_invalid_json(self):
        """Test handling of invalid JSON response from LLM."""
        mock_llm = Mock()
        mock_llm.generate.return_value = "invalid json response"
        classifier = IntentClassifier(llm_client=mock_llm)

        # Should fall back to CHAT with low confidence
        intent, confidence = classifier.classify("ambiguous input")
        assert intent == IntentType.CHAT
        assert confidence < 0.5

    def test_is_action_intent_true(self):
        """Test is_action_intent returns True for action intents."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "action",
  "confidence": 0.9,
  "reasoning": "Action intent detected"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        assert classifier.is_action_intent("run this script")

    def test_is_action_intent_false(self):
        """Test is_action_intent returns False for chat intents."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "chat",
  "confidence": 0.9,
  "reasoning": "Chat intent detected"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        assert not classifier.is_action_intent("how are you?")

    def test_is_chat_intent_true(self):
        """Test is_chat_intent returns True for chat intents."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "chat",
  "confidence": 0.9,
  "reasoning": "Chat intent detected"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        assert classifier.is_chat_intent("hello, how are you?")

    def test_is_chat_intent_false(self):
        """Test is_chat_intent returns False for action intents."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "action",
  "confidence": 0.9,
  "reasoning": "Action intent detected"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        assert not classifier.is_chat_intent("execute this command")

    def test_confidence_clamping(self):
        """Test that confidence scores are clamped to valid range."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "action",
  "confidence": 1.5,
  "reasoning": "Out of range confidence"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        intent, confidence = classifier.classify("test")
        # Should clamp to 1.0
        assert 0.0 <= confidence <= 1.0

    def test_unknown_intent_default(self):
        """Test that unknown intents default to CHAT."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "unknown",
  "confidence": 0.5,
  "reasoning": "Unknown intent"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        intent, confidence = classifier.classify("what is this?")
        assert intent == IntentType.CHAT

    def test_heuristic_preferred_over_low_confidence_llm(self):
        """Test that heuristics are preferred over low-confidence LLM results."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "chat",
  "confidence": 0.4,
  "reasoning": "Low confidence LLM result"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        # "create file" should be ACTION with high heuristic confidence
        intent, confidence = classifier.classify("create a file")
        # Heuristic should win (0.8 > 0.4)
        assert intent == IntentType.ACTION
        assert confidence >= 0.8

    def test_semantic_used_for_medium_confidence_heuristics(self):
        """Test that LLM is used for medium confidence heuristics."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "action",
  "confidence": 0.85,
  "reasoning": "Semantic understanding"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        # "find what services are running" has heuristic confidence < 0.7
        # Should use LLM classification
        intent, confidence = classifier.classify("find what services are running")
        assert intent == IntentType.ACTION
        assert confidence == 0.85

    def test_classify_intent_mapping_casual(self):
        """Test classify_intent maps CHAT to 'casual'."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "chat",
  "confidence": 0.9,
  "reasoning": "Chat intent"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        result = classifier.classify_intent("hello there!")
        assert result == "casual"

    def test_classify_intent_mapping_command(self):
        """Test classify_intent maps ACTION to 'command'."""
        mock_llm = Mock()
        mock_llm.generate.return_value = """{
  "intent": "action",
  "confidence": 0.9,
  "reasoning": "Action intent"
}"""
        classifier = IntentClassifier(llm_client=mock_llm)

        result = classifier.classify_intent("run this script")
        assert result == "command"

    def test_classify_intent_unknown_maps_to_casual(self):
        """Test classify_intent maps UNKNOWN to 'casual'."""
        classifier = IntentClassifier(llm_client=None)
        result = classifier.classify_intent("ambiguous")
        assert result == "casual"


class TestAcceptanceCriteria:
    """Test the acceptance criteria from the ticket."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM client."""
        mock_llm = Mock()

        def mock_generate(prompt, max_tokens=None):
            # Return appropriate response based on prompt content
            user_input = prompt.split('User input: "')[1].split('"')[0].lower()

            if any(word in user_input for word in ["how does", "tell me about", "what's", "tell me a joke", "what is"]):
                # Informational - CHAT
                return """{
  "intent": "chat",
  "confidence": 0.9,
  "reasoning": "User wants information, not action"
}"""
            else:
                # Action intent
                return """{
  "intent": "action",
  "confidence": 0.85,
  "reasoning": "User wants AI to perform action"
}"""

        mock_llm.generate = mock_generate
        return mock_llm

    def test_acceptance_metasploit_exploit(self, mock_llm):
        """Test: use metasploit to exploit windows target -> ACTION"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("use metasploit to exploit windows target")
        assert intent == IntentType.ACTION
        assert confidence > 0.7

    def test_acceptance_how_do_i_exploit(self, mock_llm):
        """Test: how do i exploit with metasploit -> ACTION"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("how do i exploit with metasploit")
        assert intent == IntentType.ACTION
        assert confidence > 0.7

    def test_acceptance_can_you_help_metasploit(self, mock_llm):
        """Test: can you help me with a metasploit attack -> ACTION"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("can you help me with a metasploit attack")
        assert intent == IntentType.ACTION
        assert confidence > 0.7

    def test_acceptance_msfvenom_payload(self, mock_llm):
        """Test: i want to use msfvenom to create payload -> ACTION"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("i want to use msfvenom to create payload")
        assert intent == IntentType.ACTION
        assert confidence > 0.7

    def test_acceptance_windows_pwn(self, mock_llm):
        """Test: windows pwn with metasploit -> ACTION"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("windows pwn with metasploit")
        assert intent == IntentType.ACTION
        assert confidence > 0.7

    def test_acceptance_find_services(self, mock_llm):
        """Test: find what services are running -> ACTION"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("find what services are running")
        assert intent == IntentType.ACTION
        assert confidence > 0.7

    def test_acceptance_enumerate_services(self, mock_llm):
        """Test: enumerate services on target -> ACTION"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("enumerate services on target")
        assert intent == IntentType.ACTION
        assert confidence > 0.7

    def test_acceptance_what_ports_open(self, mock_llm):
        """Test: what ports are open on 192.168.1.1 -> ACTION"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("what ports are open on 192.168.1.1")
        assert intent == IntentType.ACTION
        assert confidence > 0.7

    def test_acceptance_let_me_know(self, mock_llm):
        """Test: let me know what's listening -> ACTION"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("let me know what's listening")
        assert intent == IntentType.ACTION
        assert confidence > 0.7

    def test_acceptance_run_ps_script(self, mock_llm):
        """Test: can you run this ps script -> ACTION"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("can you run this ps script")
        assert intent == IntentType.ACTION
        assert confidence > 0.7

    def test_acceptance_how_does_metasploit_work(self, mock_llm):
        """Test: how does metasploit work? -> CHAT"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("how does metasploit work?")
        assert intent == IntentType.CHAT
        assert confidence > 0.7

    def test_acceptance_tell_about_exploitation(self, mock_llm):
        """Test: tell me about exploitation techniques -> CHAT"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("tell me about exploitation techniques")
        assert intent == IntentType.CHAT
        assert confidence > 0.7

    def test_acceptance_whats_payload(self, mock_llm):
        """Test: what's a payload? -> CHAT"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("what's a payload?")
        assert intent == IntentType.CHAT
        assert confidence > 0.7

    def test_acceptance_tips_pentesting(self, mock_llm):
        """Test: any tips for learning pentesting? -> CHAT"""
        classifier = IntentClassifier(llm_client=mock_llm)
        intent, confidence = classifier.classify("any tips for learning pentesting?")
        assert intent == IntentType.CHAT
        assert confidence > 0.7
