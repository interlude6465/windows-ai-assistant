"""
Research intent handler for integrating web research into chat flow.

Handles RESEARCH and RESEARCH_AND_ACT execution modes by coordinating
web research and optional execution.
"""

import logging
from typing import Optional, Union

from spectral.config import JarvisConfig, SpectralConfig
from spectral.execution_models import ExecutionMode
from spectral.execution_router import ExecutionRouter
from spectral.llm_client import LLMClient
from spectral.research import KnowledgePack, ResearchOrchestrator

logger = logging.getLogger(__name__)


class ResearchIntentHandler:
    """Handle research intents from user queries."""

    def __init__(
        self,
        config: Optional[Union[SpectralConfig, JarvisConfig]] = None,
        research_orchestrator: Optional[ResearchOrchestrator] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Initialize research intent handler.

        Args:
            config: Spectral/Jarvis configuration (for ResearchOrchestrator
                initialization)
            research_orchestrator: ResearchOrchestrator instance (creates default
                from config if None)
            llm_client: LLM client for generating actionable code
        """
        self.research_orchestrator = research_orchestrator or ResearchOrchestrator(config=config)
        self.router = ExecutionRouter()
        self.llm_client = llm_client
        logger.info("ResearchIntentHandler initialized")

    def should_research(self, user_input: str) -> bool:
        """
        Check if user input requires research.

        Args:
            user_input: User's natural language request

        Returns:
            True if research is needed
        """
        mode, confidence = self.router.classify(user_input)
        return (
            mode in [ExecutionMode.RESEARCH, ExecutionMode.RESEARCH_AND_ACT] and confidence >= 0.6
        )

    def handle_research_query(self, user_input: str) -> tuple[str, Optional[KnowledgePack]]:
        """
        Handle research query and format response.

        Args:
            user_input: User's research query

        Returns:
            Tuple of (formatted_response, knowledge_pack)
        """
        logger.info(f"Handling research query: {user_input}")

        mode, confidence = self.router.classify(user_input)

        try:
            pack = self.research_orchestrator.run_research(user_input, max_pages=5)

            if pack.confidence < 0.3:
                msg = (
                    f"I searched the web but couldn't find reliable "
                    f"information about: {user_input}\n\n"
                    "The sources I found had low confidence. "
                    "Could you rephrase your question or provide more details?"
                )
                return msg, pack

            response = self._format_knowledge_pack(pack, mode)

            # For RESEARCH_AND_ACT mode, generate actionable code based on research
            if mode == ExecutionMode.RESEARCH_AND_ACT:
                code_response = self._generate_actionable_code(user_input, pack)
                if code_response:
                    response += "\n\n" + code_response

            return response, pack

        except Exception as e:
            logger.error(f"Research failed: {e}")
            response = (
                f"I encountered an error while researching: {user_input}\n\n"
                f"Error: {str(e)}\n\n"
                "You can try rephrasing your question or ask me something else."
            )
            return response, None

    def _generate_actionable_code(self, user_input: str, pack: KnowledgePack) -> Optional[str]:
        """
        Generate actionable code based on research results.

        Args:
            user_input: Original user query
            pack: KnowledgePack with research results

        Returns:
            Generated code string or None if not applicable
        """
        try:
            if not self.llm_client:
                logger.warning("No LLM client available for code generation")
                return None

            # Extract key information from research
            commands = pack.commands or []
            steps = pack.steps or []

            if not commands and not steps:
                return None

            # Build context for code generation
            context_parts = []

            if commands:
                context_parts.append("Commands from research:")
                for cmd in commands[:5]:  # Limit to first 5 commands
                    command_text = cmd.get("command_text", "")
                    description = cmd.get("description", "")
                    platform = cmd.get("platform", "")
                    if command_text:
                        context_parts.append(f"- {command_text}")
                        if description:
                            context_parts.append(f"  Purpose: {description}")
                        if platform:
                            context_parts.append(f"  Platform: {platform}")

            if steps:
                context_parts.append("\nSteps from research:")
                for step in steps[:5]:  # Limit to first 5 steps
                    title = step.get("title", "")
                    description = step.get("description", "")
                    if title:
                        context_parts.append(f"- {title}")
                    if description:
                        context_parts.append(f"  Description: {description}")

            research_context = "\n".join(context_parts)

            # Generate code that uses the research findings
            prompt = (
                f'Based on the following research about "{user_input}", '
                "generate Python code that implements or demonstrates the concepts found:\n\n"
                f"Research findings:\n{research_context}\n\n"
                "Requirements:\n"
                "1. Generate actual, working Python code\n"
                "2. Use the commands and steps from the research where applicable\n"
                "3. Include proper error handling\n"
                "4. Add comments explaining how this relates to the research\n"
                "5. If the research contains specific commands, show how to use them in Python\n"
                "6. Focus on practical, executable examples\n"
                "7. Include any necessary installation instructions at the top\n\n"
                "Generate code that helps the user accomplish their goal based on what we "
                "researched. Start with a brief explanation of what the code does, then "
                "provide the actual code."
            )

            code_response = self.llm_client.generate(prompt)

            # Clean up the response and format it nicely
            if code_response:
                # Add a header to make it clear this is actionable code
                formatted_response = f"**Actionable Code Based on Research:**\n\n{code_response}"
                logger.info("Successfully generated actionable code from research")
                return formatted_response

            return None

        except Exception as e:
            logger.error(f"Failed to generate actionable code: {e}")
            return None

    def _format_knowledge_pack(self, pack: KnowledgePack, mode: ExecutionMode) -> str:
        """
        Format knowledge pack into user-friendly response.

        Args:
            pack: KnowledgePack to format
            mode: Execution mode (RESEARCH or RESEARCH_AND_ACT)

        Returns:
            Formatted response string
        """
        lines = []

        lines.append(f"📚 Research Results: {pack.goal}\n")

        if pack.assumptions:
            lines.append("**Assumptions:**")
            for assumption in pack.assumptions:
                lines.append(f"  • {assumption}")
            lines.append("")

        if pack.steps:
            lines.append("**Steps:**")
            for i, step in enumerate(pack.steps, start=1):
                title = step.get("title", f"Step {i}")
                description = step.get("description", "")
                lines.append(f"{i}. **{title}**")
                if description:
                    lines.append(f"   {description}")
            lines.append("")

        if pack.commands:
            lines.append("**Commands:**")
            for cmd in pack.commands:
                command_text = cmd.get("command_text", "")
                description = cmd.get("description", "")
                platform = cmd.get("platform", "")
                if platform:
                    lines.append(f"  [{platform}] `{command_text}`")
                else:
                    lines.append(f"  `{command_text}`")
                if description:
                    lines.append(f"     → {description}")
            lines.append("")

        if pack.file_paths:
            lines.append("**Important Files:**")
            for file_info in pack.file_paths:
                path = file_info.get("path", "")
                purpose = file_info.get("purpose", "")
                lines.append(f"  • {path}")
                if purpose:
                    lines.append(f"     {purpose}")
            lines.append("")

        if pack.settings:
            lines.append("**Settings:**")
            for setting in pack.settings:
                name = setting.get("name", "")
                value = setting.get("value", "")
                location = setting.get("location", "")
                lines.append(f"  • {name} = {value}")
                if location:
                    lines.append(f"     (in {location})")
            lines.append("")

        if pack.common_errors:
            lines.append("**Common Errors & Solutions:**")
            for error in pack.common_errors:
                error_msg = error.get("error_message", "")
                fix = error.get("fix", "")
                lines.append(f"  ❌ {error_msg}")
                if fix:
                    lines.append(f"     ✅ {fix}")
            lines.append("")

        if pack.sources:
            lines.append("**Sources:**")
            for i, source in enumerate(pack.sources[:5], start=1):
                lines.append(f"  [{i}] {source.title}")
                lines.append(f"      {source.url}")
            lines.append("")

        lines.append(f"Confidence: {pack.confidence:.0%}")

        if mode == ExecutionMode.RESEARCH_AND_ACT:
            lines.append("\n💡 **Next:** I can help you execute these steps. Just ask!")

        return "\n".join(lines)
