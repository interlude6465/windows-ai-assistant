"""
Dual execution orchestrator module.

Coordinates the dual execution mode system: routing, direct execution,
complex step breakdown, monitoring, and adaptive fixing.
"""

import logging
from typing import Callable, Generator, Optional

from spectral.adaptive_fixing import AdaptiveFixEngine
from spectral.code_step_breakdown import CodeStepBreakdown
from spectral.direct_executor import DirectExecutor
from spectral.execution_models import CodeStep, ExecutionMode
from spectral.execution_monitor import ExecutionMonitor
from spectral.execution_router import ExecutionRouter
from spectral.llm_client import LLMClient
from spectral.mistake_learner import MistakeLearner
from spectral.persistent_memory import MemoryModule
from spectral.research_intent_handler import ResearchIntentHandler
from spectral.retry_parsing import format_attempt_progress, parse_retry_limit
from spectral.utils import AUTONOMOUS_CODE_REQUIREMENT, SmartInputHandler, clean_code

logger = logging.getLogger(__name__)


class DualExecutionOrchestrator:
    """
    Orchestrates dual execution mode system.

    Routes requests to DIRECT or PLANNING mode:
    - DIRECT: Simple code gen + run via DirectExecutor
    - PLANNING: Complex multi-step via CodeStepBreakdown + ExecutionMonitor + AdaptiveFixEngine
    """

    def __init__(
        self,
        llm_client: LLMClient,
        mistake_learner: Optional[MistakeLearner] = None,
        memory_module: Optional[MemoryModule] = None,
        gui_callback: Optional[Callable[..., None]] = None,
    ) -> None:
        """
        Initialize dual execution orchestrator.

        Args:
            llm_client: LLM client for code generation and analysis
            mistake_learner: Mistake learner for storing and retrieving patterns
            memory_module: Optional memory module for tracking executions
            gui_callback: Optional callback for sandbox viewer updates
        """
        self.llm_client = llm_client
        self.mistake_learner = mistake_learner or MistakeLearner()
        self.memory_module = memory_module
        self.gui_callback = gui_callback
        self.router = ExecutionRouter()
        self.direct_executor = DirectExecutor(
            llm_client, self.mistake_learner, memory_module, gui_callback
        )
        self.code_step_breakdown = CodeStepBreakdown(llm_client)
        self.execution_monitor = ExecutionMonitor()
        self.execution_monitor.set_gui_callback(gui_callback)
        self.adaptive_fix_engine = AdaptiveFixEngine(llm_client, self.mistake_learner)
        self.research_handler = ResearchIntentHandler()
        logger.info("DualExecutionOrchestrator initialized")

    def process_request(
        self, user_input: str, max_attempts: Optional[int] = None
    ) -> Generator[str, None, None]:
        """Process user request with dual execution modes.

        Args:
            user_input: User's natural language request
            max_attempts: User-specified maximum retry attempts. None means unlimited.

        Yields:
            Status updates and output as execution progresses
        """
        logger.info(f"Processing request: {user_input}")

        if max_attempts is None:
            parsed = parse_retry_limit(user_input)
            max_attempts = parsed if parsed is not None else 15

        # Route to appropriate execution mode
        mode, confidence = self.router.classify(user_input)

        if mode == ExecutionMode.RESEARCH:
            logger.info("Using RESEARCH mode")
            yield from self._execute_research_mode(user_input)
        elif mode == ExecutionMode.RESEARCH_AND_ACT:
            logger.info("Using RESEARCH_AND_ACT mode")
            yield from self._execute_research_and_act_mode(user_input, max_attempts=max_attempts)
        elif mode == ExecutionMode.DIRECT and confidence >= 0.6:
            logger.info("Using DIRECT execution mode")
            yield from self._execute_direct_mode(user_input, max_attempts=max_attempts)
        else:
            logger.info("Using PLANNING execution mode")
            yield from self._execute_planning_mode(user_input, max_attempts=max_attempts)

    def _execute_direct_mode(
        self, user_input: str, max_attempts: Optional[int]
    ) -> Generator[str, None, None]:
        """Execute in DIRECT mode (single-step code gen + run, with retries)."""

        logger.info("Executing in DIRECT mode")

        try:
            for output in self.direct_executor.execute_request(
                user_input, max_attempts=max_attempts
            ):
                yield output
        except Exception as e:
            logger.error(f"DIRECT mode execution failed: {e}")
            yield f"\n❌ Error: {str(e)}\n"

    def _execute_research_mode(self, user_input: str) -> Generator[str, None, None]:
        """Execute in RESEARCH mode (information gathering)."""
        logger.info(f"Executing in RESEARCH mode: {user_input}")
        yield f"🔍 Researching: {user_input}...\n"

        try:
            research_response, _ = self.research_handler.handle_research_query(user_input)
            yield f"\n{research_response}\n"
        except Exception as e:
            logger.error(f"RESEARCH mode failed: {e}")
            yield f"\n❌ Research failed: {str(e)}\n"

    def _execute_research_and_act_mode(
        self, user_input: str, max_attempts: Optional[int] = None
    ) -> Generator[str, None, None]:
        """Execute in RESEARCH_AND_ACT mode (research then execute)."""
        logger.info(f"Executing in RESEARCH_AND_ACT mode: {user_input}")
        yield f"🔍 Step 1: Researching {user_input}...\n"

        try:
            research_response, pack = self.research_handler.handle_research_query(user_input)
            yield "   ✓ Research complete\n\n"

            yield "🚀 Step 2: Executing based on research findings...\n"

            # Inject research into prompt
            augmented_input = f"""
User Request: {user_input}

Research Findings:
{research_response}

Please complete the user request using the research findings provided above.
"""
            # Route based on complexity
            mode, confidence = self.router.classify(user_input)
            if mode == ExecutionMode.PLANNING or len(user_input.split()) > 10:
                yield from self._execute_planning_mode(augmented_input, max_attempts=max_attempts)
            else:
                yield from self._execute_direct_mode(augmented_input, max_attempts=max_attempts)

        except Exception as e:
            logger.error(f"RESEARCH_AND_ACT mode failed: {e}")
            yield f"\n❌ Research and Act failed: {str(e)}\n"

    def _execute_planning_mode(
        self, user_input: str, max_attempts: Optional[int]
    ) -> Generator[str, None, None]:
        """Execute in PLANNING mode (multi-step with adaptive fixing and retries)."""

        logger.info("Executing in PLANNING mode")

        try:
            # Break down request into steps
            yield "📋 Planning steps...\n"
            steps = self.code_step_breakdown.breakdown_request(user_input)

            yield f"  Created {len(steps)} step(s)\n"
            for step in steps:
                yield f"  Step {step.step_number}: {step.description}\n"
            yield "\n"

            # Execute each step with monitoring and adaptive fixing
            yield "▶️ Starting execution...\n\n"

            completed_steps = 0
            for step in steps:
                step.max_retries = max_attempts

                yield f"▶️ Step {step.step_number}/{len(steps)}: {step.description}\n"

                if not step.is_code_execution:
                    completed_steps += 1
                    step.status = "completed"
                    yield "   ✓ Informational step (no execution required)\n\n"
                    continue

                # Generate code for this step if needed
                if not step.code:
                    yield "   Generating code...\n"
                    step.code = self._generate_step_code(step, user_input)
                    yield "   ✓ Code generated\n"

                # Apply Smart Input Detection & Injection
                input_handler = SmartInputHandler()
                step.code, test_inputs = input_handler.detect_and_inject_inputs(step.code)
                if test_inputs:
                    yield f"   🧠 Smart Input: Auto-injecting {len(test_inputs)} values\n"
                    step.code = input_handler.inject_test_inputs(step.code, test_inputs)

                attempt = 1
                while True:
                    progress = format_attempt_progress(attempt, max_attempts)
                    yield f"   {progress}\n"

                    try:
                        error_detected = False
                        error_output = ""
                        full_output = ""

                        for line, is_error, error_msg in self.execution_monitor.execute_step(step):
                            full_output += line
                            yield f"   {line}"
                            if is_error:
                                error_detected = True
                                error_output += line
                                if not line.endswith("\n"):
                                    error_output += "\n"

                        if not error_detected:
                            completed_steps += 1
                            step.status = "completed"
                            yield f"   ✓ Step completed successfully on {progress}\n\n"
                            break

                        yield f"   ❌ Error detected in step {step.step_number} ({progress})\n"

                        # Parse error
                        error_type, error_details = self.execution_monitor.parse_error_from_output(
                            error_output or full_output
                        )
                        yield f"   Error type: {error_type}\n"
                        yield "   Diagnosing failure...\n"

                        diagnosis = self.adaptive_fix_engine.diagnose_failure(
                            step, error_type, error_details, full_output
                        )
                        yield f"   Root cause: {diagnosis.root_cause}\n"
                        yield f"   🔧 Fixing: {diagnosis.suggested_fix}\n"

                        # Check if we should abort due to repeated failures
                        if self.adaptive_fix_engine.should_abort_retry(
                            step.step_number,
                            error_type,
                            attempt,
                            diagnosis.fix_strategy,
                            max_attempts,
                        ):
                            step.status = "failed"
                            yield "   ❌ Aborting due to repeated failures or retry limit\n\n"
                            break

                        # For ImportError on external packages, prefer stdlib fallback
                        if (
                            error_type == "ImportError"
                            and diagnosis.fix_strategy == "install_package"
                        ):
                            yield (
                                "   ⚠️  Import error detected - will try stdlib-only "
                                "solution instead of external package\n"
                            )
                            # Override fix strategy to regenerate code with stdlib only
                            diagnosis.fix_strategy = "stdlib_fallback"
                            diagnosis.suggested_fix = "Rewrite using only Python standard library"

                        yield "   Applying fix...\n"
                        fixed_code = self.adaptive_fix_engine.generate_fix(
                            step, diagnosis, attempt - 1
                        )
                        step.code = fixed_code
                        step.status = "retrying"

                        attempt += 1
                        yield f"   ▶️ Retrying step {step.step_number}...\n\n"
                        continue

                    except Exception as e:
                        logger.error(f"Exception during step execution: {e}")

                        if max_attempts is not None and attempt >= max_attempts:
                            yield f"   ❌ Step failed: {str(e)}\n\n"
                            step.status = "failed"
                            break

                        yield f"   ❌ Exception on {progress}: {str(e)}\n"
                        attempt += 1
                        yield "   ▶️ Retrying...\n\n"
                        continue

                # If step failed and it has dependencies, abort
                if step.status == "failed":
                    yield "   ⚠️  Aborting execution due to failed step\n"
                    break

            # Final summary
            yield "\n✅ Execution complete\n"
            yield f"   Completed: {completed_steps}/{len(steps)} steps\n"

        except Exception as e:
            logger.error(f"PLANNING mode execution failed: {e}")
            yield f"\n❌ Error: {str(e)}\n"

    def _generate_step_code(self, step: CodeStep, user_input: str) -> str:
        """
        Generate code for a step.

        Args:
            step: CodeStep to generate code for
            user_input: Original user request

        Returns:
            Generated code
        """
        import getpass

        username = getpass.getuser()

        prompt = f"""{AUTONOMOUS_CODE_REQUIREMENT}

Task: Write Python code to accomplish this step:
{step.description}

Original Request: {user_input}

Remember:
- Hard-code all input values
- No input() calls
- Code must run autonomously
- Produce output immediately

IMPORTANT: You are running on Windows. Always use Windows paths:
- Home directory: C:\\Users\\{username}
- Desktop: C:\\Users\\{username}\\Desktop
- Temp: C:\\Users\\{username}\\AppData\\Local\\Temp

NEVER use:
- /path/to/... (Unix paths)
- /usr/bin, /home, /var (Unix directories)
- Relative paths like './data' (use full Windows paths)

For file operations, use:
- os.path.expanduser('~') for home directory
- os.path.join() for path construction
- Always use backslashes or raw strings: r'C:\\path\\to\\file'

General Requirements:
- Write complete, executable code
- Include proper error handling
- Add comments explaining the code
- Make it production-ready
- No extra text or explanations, just the code
- Return only the code, no markdown formatting, no explanations."""

        try:
            raw_code = self.llm_client.generate(prompt)
            code = clean_code(str(raw_code))
            logger.debug(f"Generated code for step {step.step_number}: {len(code)} characters")
            return str(code)
        except Exception as e:
            logger.error(f"Failed to generate code for step {step.step_number}: {e}")
            raise

    def get_execution_mode(self, user_input: str) -> ExecutionMode:
        """
        Get the execution mode for a user request.

        Args:
            user_input: User's natural language request

        Returns:
            ExecutionMode (DIRECT or PLANNING)
        """
        mode, _ = self.router.classify(user_input)
        return ExecutionMode(mode)
