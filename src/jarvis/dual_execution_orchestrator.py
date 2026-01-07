"""
Dual execution orchestrator module.

Coordinates the dual execution mode system: routing, direct execution,
complex step breakdown, monitoring, and adaptive fixing.
"""

import logging
from typing import Generator, Optional

from jarvis.adaptive_fixing import AdaptiveFixEngine
from jarvis.code_step_breakdown import CodeStepBreakdown
from jarvis.direct_executor import DirectExecutor
from jarvis.execution_models import CodeStep, ExecutionMode
from jarvis.execution_monitor import ExecutionMonitor
from jarvis.execution_router import ExecutionRouter
from jarvis.llm_client import LLMClient
from jarvis.mistake_learner import MistakeLearner
from jarvis.persistent_memory import MemoryModule
from jarvis.retry_parsing import format_attempt_progress, parse_retry_limit
from jarvis.utils import clean_code

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
        gui_callback: Optional[callable] = None,
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
            max_attempts = parse_retry_limit(user_input)

        # Route to appropriate execution mode
        mode, confidence = self.router.classify(user_input)

        if mode == ExecutionMode.DIRECT and confidence >= 0.6:
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
        prompt = f"""Write Python code to accomplish this step:

Step Description: {step.description}

Original Request: {user_input}

Requirements:
- Write complete, executable code
- Include proper error handling
- Add comments explaining the code
- Make it production-ready
- No extra text or explanations, just the code
- IMPORTANT: For interactive programs, use input() and print(), NOT Tkinter dialogs
- AVOID: simpledialog.askstring, simpledialog.askfloat, simpledialog.askinteger, tkinter.filedialog
- Use CLI-based input() instead: input("Enter value: ")

Return only the code, no markdown formatting, no explanations."""

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
