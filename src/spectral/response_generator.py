"""
Response generator module for natural conversational responses.

Generates friendly responses for casual conversation and summaries for commands.
"""

import logging
import re
from typing import Generator, List, Optional, Tuple

from spectral.capability_system import get_capability_announcement
from spectral.conversation_context import ConversationContext
from spectral.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """
    Generates natural conversational responses based on intent.

    For casual intents: Uses LLM to generate warm, friendly responses
    For command intents: Generates summaries of what was executed
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        conversation_memory: Optional[ConversationContext] = None,
    ) -> None:
        """
        Initialize response generator.

        Args:
            llm_client: Optional LLM client for generating conversational responses
            conversation_memory: Optional conversation memory for context-aware responses
        """
        self.llm_client = llm_client
        self.conversation_memory = conversation_memory
        self.conversation_history: List[dict] = []
        logger.info("ResponseGenerator initialized")

    def generate_response(
        self,
        intent: str,
        execution_result: str,
        original_input: str,
        memory_context: Optional[str] = None,
    ) -> str:
        """
        Generate an appropriate response based on intent and context.

        Args:
            intent: "casual" or "command"
            execution_result: Result from execution (for commands)
            original_input: Original user input
            memory_context: Optional memory context from previous conversations

        Returns:
            Generated response string
        """
        if intent == "casual":
            response = self._generate_casual_response(original_input, memory_context)
            self._add_to_history("user", original_input)
            self._add_to_history("assistant", response)
            return response
        else:  # command
            return self._generate_command_response(original_input, execution_result, memory_context)

    def generate_response_stream(
        self,
        intent: str,
        execution_result: str,
        original_input: str,
        memory_context: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """
        Generate an appropriate response based on intent and context with streaming.

        Args:
            intent: "casual" or "command"
            execution_result: Result from execution (for commands)
            original_input: Original user input
            memory_context: Optional memory context from previous conversations

        Yields:
            Response text chunks as they arrive
        """
        if intent == "casual":
            full_response = ""
            for chunk in self._generate_casual_response_stream(original_input, memory_context):
                full_response += chunk
                yield chunk

            self._add_to_history("user", original_input)
            self._add_to_history("assistant", full_response)
        else:  # command
            response = self._generate_command_response(
                original_input, execution_result, memory_context
            )
            yield response

    def _add_to_history(self, role: str, content: str) -> None:
        """
        Add a message to conversation history.

        Args:
            role: Message role (user or assistant)
            content: Message content
        """
        self.conversation_history.append({"role": role, "content": content})

        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    def _generate_casual_response(
        self, user_input: str, memory_context: Optional[str] = None
    ) -> str:
        """
        Generate a friendly conversational response.

        Args:
            user_input: Original user input
            memory_context: Optional memory context from previous conversations

        Returns:
            Friendly conversational response
        """
        logger.debug(f"Generating casual response for: {user_input}")

        # Check for continuation requests if we have conversation memory
        if self.conversation_memory and self.conversation_memory.detect_continuation_request(
            user_input
        ):
            context = self.conversation_memory.get_continuation_context(user_input)
            if context:
                logger.debug("Continuation request detected")
                return self._generate_continuation_response(user_input, context)

        # If no LLM client, provide simple rule-based responses
        if not self.llm_client:
            return self._get_simple_casual_response(user_input)

        # Use LLM to generate natural response
        prompt = self._build_casual_prompt(user_input, memory_context)

        try:
            response = self.llm_client.generate(prompt)
            logger.debug(f"Generated casual response: {response}")
            return str(response).strip()  # type: ignore[no-any-return]
        except Exception as e:
            logger.warning(f"Failed to generate LLM response: {e}")
            return self._get_simple_casual_response(user_input)

    def _generate_casual_response_stream(
        self, user_input: str, memory_context: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        Generate a friendly conversational response with streaming.

        Args:
            user_input: Original user input
            memory_context: Optional memory context from previous conversations

        Yields:
            Response text chunks as they arrive
        """
        logger.debug(f"Generating streaming casual response for: {user_input}")

        # Check for continuation requests if we have conversation memory
        if self.conversation_memory and self.conversation_memory.detect_continuation_request(
            user_input
        ):
            context = self.conversation_memory.get_continuation_context(user_input)
            if context:
                logger.debug("Continuation request detected")
                yield self._generate_continuation_response(user_input, context)
                return

        # If no LLM client, provide simple rule-based responses
        if not self.llm_client:
            yield self._get_simple_casual_response(user_input)
            return

        # Use LLM to generate natural response with streaming
        prompt = self._build_casual_prompt(user_input, memory_context)

        try:
            for chunk in self.llm_client.generate_stream(prompt):
                yield chunk
        except Exception as e:
            logger.warning(f"Failed to generate streaming LLM response: {e}")
            yield self._get_simple_casual_response(user_input)

    def _generate_continuation_response(self, user_input: str, context: dict) -> str:
        """
        Generate a response for a continuation request.

        Args:
            user_input: User's continuation request (e.g., "another one")
            context: Previous conversation context

        Returns:
            Continuation response
        """
        prev_user = context.get("previous_user_message", "")

        # For jokes, tell another joke
        if "joke" in prev_user.lower():
            return (
                "Here's another one: What do you call a programmer in winter? "
                "Dll! 😄 Want another one?"
            )

        # For stories or facts, provide more content
        if "tell me" in prev_user.lower() or "tell" in prev_user.lower():
            if self.llm_client:
                prompt = (
                    "The user said "
                    f'"{prev_user}" and I responded. Now they said "{user_input}".\n\n'
                    "Continue naturally with more content related to "
                    "the previous topic. Be brief (1-2 sentences) and engaging."
                )
                try:
                    response = self.llm_client.generate(prompt)
                    return str(response).strip()
                except Exception:
                    pass

            return (
                "Sure! Would you like me to tell you something similar or "
                "move on to a different topic?"
            )

        # Default continuation
        return "Here's another one! Let me know if you'd like more or something different."

    def _get_simple_casual_response(self, user_input: str) -> str:
        """
        Get a simple rule-based casual response.

        Args:
            user_input: Original user input

        Returns:
            Simple friendly response
        """
        input_lower = user_input.lower()

        # Greetings
        if any(
            word in input_lower
            for word in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
        ):
            return "Hi there! I'm doing great, thanks for asking! How can I help you today?"

        # How are you
        if any(word in input_lower for word in ["how are you", "how are you doing"]):
            return (
                "I'm doing great, thank you for asking! I'm ready to help you "
                "with any tasks you have. What would you like me to do?"
            )

        # What's your name
        if any(
            word in input_lower for word in ["what's your name", "what is your name", "who are you"]
        ):
            return (
                "I'm Spectral, your AI assistant! I can help you with "
                "various tasks like creating files, writing code, executing "
                "commands, and much more. What can I help you with?"
            )

        # How can you help
        if any(
            word in input_lower
            for word in ["how can you help", "what can you do", "help me", "capabilities"]
        ):
            return (
                "I can help you with a wide range of tasks! I can create "
                "and manage files, write and execute code, run system commands, "
                "search for information, and assist with various development tasks. "
                "Just tell me what you need!"
            )

        # Tell me a joke
        if "joke" in input_lower:
            return (
                "Why do programmers prefer dark mode? Because light "
                "attracts bugs! 😄 But seriously, how can I help you today?"
            )

        # Thank you
        if any(word in input_lower for word in ["thank", "thanks"]):
            return (
                "You're welcome! I'm always happy to help. "
                "Is there anything else you'd like me to do?"
            )

        # Default friendly response
        return "Hello! I'm here to help. What would you like me to do for you?"

    def _parse_execution_status(self, execution_result: str) -> Tuple[int, int]:
        """
        Parse execution result to count total and successful steps.

        Args:
            execution_result: String containing execution results

        Returns:
            Tuple of (total_steps, successful_steps)
        """
        total_steps = 0
        successful_steps = 0

        # Look for step completion patterns
        step_patterns = [
            r"Step (\d+).*completed successfully",
            r"✅ Step (\d+)",
            r"\[Step (\d+)\] completed",
        ]

        for pattern in step_patterns:
            matches = re.findall(pattern, execution_result, re.IGNORECASE)
            successful_steps += len(matches)
            total_steps = max(total_steps, max([int(m) for m in matches], default=0))

        # Count other completed steps
        success_indicators = [
            "✓ Step",
            "✓ Code generated",
            "✓ Execution complete",
            "✓ Successfully",
        ]

        for indicator in success_indicators:
            successful_steps += execution_result.count(indicator)

        # If we found step numbers, that's our total
        if total_steps > 0:
            return total_steps, successful_steps

        # Otherwise, estimate based on indicators
        total_steps = max(1, successful_steps)
        return total_steps, successful_steps

    def _build_partial_success_summary(
        self, original_input: str, execution_result: str, successful_steps: int, total_steps: int
    ) -> str:
        """Build a partial success summary response."""
        # Try to identify what failed from execution result
        failed_parts = []
        if "Error" in execution_result or "Failed" in execution_result:
            # Extract error lines
            lines = execution_result.split("\n")
            for line in lines:
                if "error" in line.lower() or "failed" in line.lower():
                    failed_parts.append(line.strip())

        response = f"I completed {successful_steps} out of {total_steps} steps. "

        if failed_parts:
            response += f"Had issues with: {failed_parts[0]}"
        else:
            response += "Some steps encountered issues."

        response += " Would you like me to try a different approach?"

        return response

    def _build_failure_summary(self, original_input: str, execution_result: str) -> str:
        """Build a failure summary response."""
        # Try to identify what went wrong
        error_type = "issues"
        if "ImportError" in execution_result:
            error_type = "import errors"
        elif "FileNotFoundError" in execution_result:
            error_type = "file access issues"
        elif "PermissionError" in execution_result:
            error_type = "permission issues"
        elif "SyntaxError" in execution_result:
            error_type = "syntax errors"
        elif "ConnectionError" in execution_result:
            error_type = "connection issues"
        elif "Timeout" in execution_result:
            error_type = "timeout issues"

        return (
            f"I tried to {original_input} but ran into {error_type}. "
            "Would you like me to try a different approach or provide more details?"
        )

    def _generate_command_response(
        self, original_input: str, execution_result: str, memory_context: Optional[str] = None
    ) -> str:
        """
        Generate a summary response for commands.

        For simple task results (direct output), uses LLM to present naturally.
        For complex task results (plans, executions), uses summary templates.

        Args:
            original_input: Original user command
            execution_result: Result from execution
            memory_context: Optional memory context from previous conversations

        Returns:
            Summary response
        """
        logger.debug(f"Generating command response for: {original_input}")

        # Check if this is a simple task result (direct output, not plan/execution metadata)
        # Simple results look like: "Your IP address is: 192.168.1.1" or "Files in Desktop:"
        is_simple_result = self._is_simple_task_result(execution_result)

        if is_simple_result and self.llm_client:
            # Use LLM to present simple task results naturally
            prompt = f"""The user asked: "{original_input}"

You executed this and got:
{execution_result}

Present the result naturally and conversationally. Be brief and helpful.
Format clearly if it's a list or data. Don't say "let me fetch that" or make promises.
Just present the result directly in a friendly way.

⚠️ CRITICAL: If the user asks for code, generate FULLY AUTONOMOUS code with NO interactive
input() calls. All values must be hard-coded. No input() calls allowed."""

            try:
                response = self.llm_client.generate(prompt)
                return str(response).strip()
            except Exception as e:
                logger.warning(f"Failed to generate response: {e}")
                return execution_result

        # For complex task results, use the existing summary logic
        # Parse execution result for status
        total_steps, successful_steps = self._parse_execution_status(execution_result)

        # All success
        if successful_steps == total_steps and total_steps > 0:
            return self._build_success_summary(original_input, execution_result)
        # Partial success
        elif successful_steps > 0 and successful_steps < total_steps:
            return self._build_partial_success_summary(
                original_input, execution_result, successful_steps, total_steps
            )
        # All failed
        elif successful_steps == 0 and total_steps > 0:
            return self._build_failure_summary(original_input, execution_result)
        # Unknown status (fallback)
        else:
            return self._build_neutral_summary(original_input, execution_result)

    def _is_simple_task_result(self, execution_result: str) -> bool:
        """
        Check if execution result is from a simple task (direct output).

        Args:
            execution_result: Execution result string

        Returns:
            True if this is a simple task result
        """
        # Simple task results don't contain plan/execution metadata
        # They look like direct output: "Your IP address is:", "Files in Desktop:", etc.

        # Exclude if it contains plan/execution markers
        excluded_patterns = [
            "Plan ID:",
            "Plan Execution",
            "Step Result:",
            "Execution Summary:",
            "✓ Execution Result:",
            "📋 Plan:",
            "📌 Steps:",
        ]

        result_lower = execution_result.lower()
        for pattern in excluded_patterns:
            if pattern.lower() in result_lower:
                return False

        # Check if it looks like simple task output
        simple_indicators = [
            "your ip address",
            "files in",
            "contents of",
            "command executed",
        ]

        return any(indicator in result_lower for indicator in simple_indicators)

    def _build_success_summary(self, original_input: str, execution_result: str) -> str:
        """Build a success summary response."""
        input_lower = original_input.lower()

        # Extract program type from execution result if available
        program_type = self._extract_program_type(execution_result)

        # File operations
        if any(word in input_lower for word in ["create", "write", "make", "generated", "built"]):
            if "file" in input_lower:
                return "Done! I've successfully created the file for you."
            elif "code" in input_lower or "script" in input_lower or "program" in input_lower:
                if program_type:
                    return f"✅ Finished creating {program_type}. Saved to your file system."
                return "Done! I've generated the code and executed it successfully."

        # Execution operations
        if any(word in input_lower for word in ["run", "execute", "launch", "start"]):
            return "Done! I've executed the command successfully."

        # Default success message
        return "Done! I've completed your request successfully."

    def _extract_program_type(self, execution_result: str) -> Optional[str]:
        """
        Extract program type from execution result.

        Args:
            execution_result: Execution result string

        Returns:
            Program type string or None
        """
        # Look for program type in execution result
        result_lower = execution_result.lower()

        program_types = [
            "calculator",
            "game",
            "quiz",
            "todo app",
            "converter",
            "generator",
            "notepad",
            "chatbot",
            "utility",
        ]

        for ptype in program_types:
            if ptype in result_lower:
                return ptype

        return None

    def _build_error_summary(self, original_input: str, execution_result: str) -> str:
        """Build an error summary response."""
        return (
            "I encountered an error while trying to complete your request. "
            "Please check the error details above and try again."
        )

    def _build_neutral_summary(self, original_input: str, execution_result: str) -> str:
        """Build a neutral summary response."""
        return "I've processed your request. Check the results above for details."

    def _build_casual_prompt(self, user_input: str, memory_context: Optional[str] = None) -> str:
        """
        Build prompt for casual conversation response.

        Context is included for AI understanding but should not necessarily be verbalized.
        Only reference context when directly relevant to the current question.

        Args:
            user_input: User's conversational input
            memory_context: Optional memory context from previous conversations

        Returns:
            Formatted prompt string
        """
        # Get capability announcement
        capabilities = get_capability_announcement()

        # Build conversation history section
        history_section = ""
        if self.conversation_history:
            recent_history = self.conversation_history[-5:]
            history_lines = []
            for turn in recent_history:
                role = turn.get("role", "unknown")
                content = turn.get("content", "")
                if len(content) > 200:
                    content = content[:200] + "..."
                history_lines.append(f"{role.capitalize()}: {content}")

            if history_lines:
                history_section = "Recent conversation:\n" + "\n".join(history_lines) + "\n\n"

        # Build context section if memory_context is available
        # This is for AI understanding, not verbalization
        context_section = ""
        if memory_context:
            context_section = f"[BACKGROUND: {memory_context}]\n\n"

        prompt = f"""{capabilities}

{history_section}{context_section}User: "{user_input}"

Respond naturally and conversationally. Be friendly and brief.

⚠️ CRITICAL: If the user asks for code, generate FULLY AUTONOMOUS code with NO interactive
input() calls. All values must be hard-coded. No input() calls allowed.

Only reference past conversations or context when directly relevant to the current question.
Never mention that you "remember" unless it's genuinely important to the answer.
Don't use repetitive preambles like "As I recall" or "Hello again!".
Answer their question directly or acknowledge their message appropriately.
When asked what you can do, mention your actual capabilities (code, files, commands, etc.).

Keep your response under 3 sentences unless they're asking a complex question.
Be conversational and professional."""
        return prompt
