"""
Sandbox viewer main container for all sandbox visualization panels.

Integrates:
- LiveCodeEditor: Shows code being generated (smaller font for terminal mode)
- ExecutionConsole: Shows program execution output
- TestResultsViewer: Shows test progress and results
- StatusPanel: Shows execution steps and progress
- DeploymentPanel: Shows deployment success
- TerminalEmulator: Live terminal display for metasploit execution

Features:
- Terminal mode detection (when metasploit commands run)
- Dynamic UI transformation between code view and terminal view
- Session and listener visualization
- Real-time command/output streaming
"""

import logging
import re
from typing import Optional

import customtkinter as ctk

from spectral.gui.deployment_panel import DeploymentPanel
from spectral.gui.execution_console import ExecutionConsole
from spectral.gui.live_code_editor import LiveCodeEditor
from spectral.gui.status_panel import StatusPanel
from spectral.gui.terminal_emulator import TerminalEmulator, TerminalManager
from spectral.gui.test_results_viewer import TestResultsViewer

logger = logging.getLogger(__name__)


class SandboxViewer(ctk.CTkFrame):
    """
    Main container for all sandbox visualization panels.

    Features:
    - All sub-panels integrated in a cohesive layout
    - Event routing based on event_type
    - Real-time updates via gui_callback
    - Terminal mode detection and transformation
    - Dynamic layout switching (code view ↔ terminal view)
    - Session and listener visualization
    """

    # Layout constants
    PANEL_HEIGHT = 200
    MINIMIZED_HEIGHT = 40

    def __init__(self, parent_frame, debug_mode: bool = False, **kwargs):
        """
        Initialize sandbox viewer.

        Args:
            parent_frame: Parent frame to pack into
            debug_mode: Enable debug logging
            **kwargs: Additional frame arguments
        """
        super().__init__(parent_frame, **kwargs)

        self.configure(fg_color=("#1E1E1E", "#111111"))
        self.debug_mode = debug_mode

        # State tracking
        self.is_visible = True
        self.test_id_map: dict[str, str] = {}  # Map test names to viewer test IDs
        self.current_request_id: Optional[str] = None

        # Timer for elapsed time
        self.timer_running = False
        self.timer_thread = None

        # Terminal mode state
        self.terminal_mode = False
        self.metasploit_active = False
        self.terminal_manager = TerminalManager()

        # Setup UI
        self._setup_ui()

        logger.info("SandboxViewer initialized")

    def _setup_ui(self) -> None:
        """Set up the UI layout."""
        # Main content frame - always visible (no toggle button)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)

        # Create panels in a grid layout
        self._create_panels()

    def _create_panels(self) -> None:
        """Create all visualization panels."""

        # Check if we should start in terminal mode
        if self.terminal_mode:
            self._create_terminal_panels()
        else:
            self._create_code_panels()

    def _create_code_panels(self) -> None:
        """Create panels for code view mode."""
        # Top row: Code editor (left) + Status panel (right)
        top_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        top_row.pack(fill="both", expand=True, padx=5, pady=2)

        # Code editor (main focus) - smaller font as requested
        self.code_editor = LiveCodeEditor(top_row, width=650, height=260)
        self.code_editor.pack(side="left", fill="both", expand=True, padx=(0, 2))

        # Status panel
        self.status_panel = StatusPanel(top_row, width=250, height=260)
        self.status_panel.pack(side="right", fill="both", expand=False, padx=(2, 0))

        # Middle row: Execution console
        middle_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        middle_row.pack(fill="both", expand=True, padx=5, pady=2)

        self.execution_console = ExecutionConsole(middle_row, height=260)
        self.execution_console.pack(fill="both", expand=True)

        # Bottom row: Deployment (left) + Live chat feed (right)
        bottom_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        bottom_row.pack(fill="x", padx=5, pady=2)

        self.deployment_panel = DeploymentPanel(bottom_row, height=170)
        self.deployment_panel.pack(
            side="left", fill="both", expand=True, padx=(0, 2), pady=2
        )

        # Re-using the existing TestResultsViewer slot as a compact chat feed.
        self.test_results = TestResultsViewer(bottom_row, width=320, height=170)
        self.test_results.pack(
            side="right", fill="both", expand=False, padx=(2, 0), pady=2
        )

    def _create_terminal_panels(self) -> None:
        """Create panels for terminal mode."""
        # Create terminal emulator covering most of the space
        self.terminal_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.terminal_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Create terminal emulator
        self.terminal_emulator = self.terminal_manager.create_terminal(
            "main", self.terminal_frame
        )
        self.terminal_emulator.pack(fill="both", expand=True)

        # Status panel (compact) for session info
        status_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        status_row.pack(fill="x", padx=5, pady=2)

        self.status_panel = StatusPanel(status_row, height=60)
        self.status_panel.pack(fill="x", pady=2)

    def detect_terminal_mode(self, command: str) -> bool:
        """
        Detect if a command should trigger terminal mode.

        Args:
            command: Command to analyze

        Returns:
            True if command should trigger terminal mode
        """
        # Check for metasploit-related commands
        metasploit_patterns = [
            r"\bmsfconsole\b",
            r"\bmsfvenom\b",
            r"\bmetasploit\b",
            r"\bexploit\b.*\bwindows\b",
            r"\bexploit\b.*\blinux\b",
            r"\bexploit\b.*\bsmb\b",
            r"\bexploit\b.*\bssh\b",
            r"\bhandler\b",
            r"\breverse\b.*\btcp\b",
            r"\bmeterpreter\b",
            r"\bsession\b.*\bopen\b",
            r"\b\.rc\b",  # Resource scripts
        ]

        for pattern in metasploit_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return True

        return False

    def switch_to_terminal_mode(self) -> None:
        """Switch from code view to terminal mode."""
        if self.terminal_mode:
            return

        logger.info("Switching to terminal mode")
        self.terminal_mode = True
        self.metasploit_active = True

        # Clear existing panels
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Create terminal panels
        self._create_terminal_panels()

    def switch_to_code_mode(self) -> None:
        """Switch from terminal mode to code view."""
        if not self.terminal_mode:
            return

        logger.info("Switching to code mode")
        self.terminal_mode = False
        self.metasploit_active = False

        # Stop terminal
        if hasattr(self, "terminal_manager"):
            self.terminal_manager.stop_all()

        # Clear existing panels
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Create code panels
        self._create_code_panels()

    def handle_metasploit_command(self, command: str, output_callback=None) -> None:
        """
        Handle a metasploit command with terminal display.

        Args:
            command: Command to execute
            output_callback: Callback for real-time output
        """
        # Switch to terminal mode if not already in it
        if not self.terminal_mode:
            self.switch_to_terminal_mode()

        # Show the command in terminal
        if hasattr(self, "terminal_emulator"):
            self.terminal_emulator.show_command(command)

        # Set output callback if provided
        if output_callback and hasattr(self, "terminal_emulator"):
            self.terminal_emulator.append_output = output_callback

        self.metasploit_active = True

    def update_sessions(self, sessions: dict) -> None:
        """Update active sessions display."""
        if hasattr(self, "terminal_emulator"):
            self.terminal_emulator.update_sessions(sessions)
        elif hasattr(self, "status_panel"):
            # Fallback to status panel
            session_info = f"Sessions: {len(sessions)}"
            self.status_panel.set_step(0, session_info)

    def update_listeners(self, listeners: dict) -> None:
        """Update active listeners display."""
        if hasattr(self, "terminal_emulator"):
            self.terminal_emulator.update_listeners(listeners)
        elif hasattr(self, "status_panel"):
            # Fallback to status panel
            listener_info = f"Listeners: {len(listeners)}"
            self.status_panel.set_step(0, listener_info)

    def handle_gui_callback(self, event_type: str, data: dict) -> None:
        """
        Handle gui_callback events and update panels.

        Args:
            event_type: Type of event
            data: Event data dictionary
        """
        if self.debug_mode:
            logger.debug(f"SandboxViewer received event: {event_type}, data: {data}")

        handlers = {
            # Code events
            "code_generation_started": self._on_code_generation_started,
            "code_chunk_generated": self._on_code_chunk_generated,
            "code_generated": self._on_code_generated,
            "code_generation_complete": self._on_code_generation_complete,
            # Sandbox events
            "sandbox_created": self._on_sandbox_created,
            "sandbox_cleaned": self._on_sandbox_cleaned,
            # Analysis events
            "program_analyzed": self._on_program_analyzed,
            # Prompt events
            "prompts_injected": self._on_prompts_injected,
            # Test events
            "test_cases_generated": self._on_test_cases_generated,
            "test_started": self._on_test_started,
            "test_completed": self._on_test_completed,
            "test_result": self._on_test_result,
            "test_summary": self._on_test_summary,
            # Execution events
            "execution_line": self._on_execution_line,
            "prompt_detected": self._on_prompt_detected,
            "input_sent": self._on_input_sent,
            "test_output": self._on_test_output,
            # Chat feed events
            "chat_feed_append": self._on_chat_feed_append,
            "chat_feed_clear": self._on_chat_feed_clear,
            # Deployment events
            "deployment_started": self._on_deployment_started,
            "deployment_complete": self._on_deployment_complete,
            # Step events
            "step_progress": self._on_step_progress,
            "retry_attempt": self._on_retry_attempt,
            # Error events
            "error_occurred": self._on_error_occurred,
            # Metasploit events
            "metasploit_command": self._on_metasploit_command,
            "metasploit_output": self._on_metasploit_output,
            "session_created": self._on_session_created,
            "listener_started": self._on_listener_started,
        }

        handler = handlers.get(event_type)
        if handler:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Error handling event {event_type}: {e}")
        else:
            if self.debug_mode:
                logger.debug(f"No handler for event: {event_type}")

    # Event handlers
    def _on_code_generation_started(self, data: dict) -> None:
        """Handle code generation started."""
        self.code_editor.clear()
        self.execution_console.log_info("Code generation started...")
        self.status_panel.start_timer()

        # Extract request_id if available
        request_id = data.get("request_id")
        if request_id:
            self.current_request_id = request_id
            from datetime import datetime

            self.code_editor.set_metadata(
                request_id, timestamp=datetime.now().strftime("%H:%M:%S")
            )

    def _on_code_chunk_generated(self, data: dict) -> None:
        """Handle code chunk generated (for streaming)."""
        chunk = data.get("chunk", "")
        if chunk:
            # Append code with highlight
            self.code_editor.append_code(chunk)
            # Highlight the new chunk
            self.code_editor.highlight_last_chunk(chunk)

    def _on_code_generated(self, data: dict) -> None:
        """Handle code generated."""
        code = data.get("code", "")
        if code:
            # Remove chunk highlights when final code is set
            self.code_editor.dehighlight_last_chunk()

            # Ensure the full code is visible even when generation wasn't streamed.
            self.code_editor.set_code(code)

            # Update file path if available
            file_path = data.get("file_path")
            request_id = data.get("request_id", self.current_request_id or "unknown")

            if file_path:
                from datetime import datetime

                self.code_editor.set_metadata(
                    request_id,
                    timestamp=datetime.now().strftime("%H:%M:%S"),
                    file_path=file_path,
                )

            line_count = len(code.split("\n"))
            self.execution_console.log_info(f"Code generated ({line_count} lines)")

    def _on_code_generation_complete(self, data: dict) -> None:
        """Handle code generation complete."""
        self.code_editor.dehighlight_last_chunk()
        self.execution_console.log_info("Code generation complete")

    def _on_sandbox_created(self, data: dict) -> None:
        """Handle sandbox created."""
        sandbox_id = data.get("sandbox_id", "unknown")
        self.execution_console.log_info(f"Sandbox created: {sandbox_id}")
        self.status_panel.mark_step_complete(1)

    def _on_sandbox_cleaned(self, data: dict) -> None:
        """Handle sandbox cleaned."""
        self.execution_console.log_info("Sandbox cleaned up")
        self.status_panel.mark_step_complete(7)

    def _on_program_analyzed(self, data: dict) -> None:
        """Handle program analyzed."""
        analysis = data.get("analysis", {})
        program_type = analysis.get("program_type", "unknown")
        self.execution_console.log_info(f"Program type detected: {program_type}")
        self.status_panel.mark_step_complete(2)

    def _on_prompts_injected(self, data: dict) -> None:
        """Handle prompts injected."""
        count = data.get("count", 0)
        code_preview = data.get("code_preview", "")[:100]
        self.execution_console.log_info(f"Prompts injected: {count}")
        if code_preview:
            self.execution_console.log_info(f"Preview: {code_preview}...")
        self.status_panel.mark_step_complete(4)

    def _on_test_cases_generated(self, data: dict) -> None:
        """Handle test cases generated."""
        count = data.get("count", 0)
        tests = data.get("tests", [])

        # Reset test stats (keep the chat feed transcript intact)
        self.test_results.reset_tests()
        self.test_id_map.clear()

        # Add new tests
        for test in tests:
            test_id = self.test_results.add_test(
                name=test.get("name", "Unnamed test"),
                inputs=test.get("inputs", []),
                expected=test.get("expected", ""),
            )
            self.test_id_map[test.get("name", "unknown")] = test_id

        self.execution_console.log_info(f"Generated {count} test cases")
        self.status_panel.mark_step_complete(5)

    def _on_test_started(self, data: dict) -> None:
        """Handle test started."""
        test_name = data.get("test_name", "Unknown")
        test_num = data.get("test_num", 0)

        if test_name in self.test_id_map:
            self.test_results.update_test_running(self.test_id_map[test_name])

        self.execution_console.log_info(f"Running test: {test_name} ({test_num})")
        self.status_panel.mark_step_complete(6)

    def _on_test_completed(self, data: dict) -> None:
        """Handle test completed."""
        test_name = data.get("test_name", "Unknown")
        result = data.get("result", {})
        passed = result.get("passed", False)
        output = result.get("output", "")[:100]
        elapsed = result.get("elapsed_time", 0)

        if test_name in self.test_id_map:
            test_id = self.test_id_map[test_name]
            if passed:
                self.test_results.update_test_passed(test_id, output, elapsed)
            else:
                error = result.get("error", "Test failed")
                self.test_results.update_test_failed(test_id, error)

    def _on_test_result(self, data: dict) -> None:
        """Handle test result (from sandbox_execution_system)."""
        test_num = data.get("test_num", 0)
        result = data.get("result", {})

        passed = result.get("passed", False)
        test_name = result.get("test_name", f"Test {test_num}")
        output = result.get("output", "")[:100]
        elapsed = result.get("elapsed_time", 0)

        if passed:
            self.execution_console.log_info(f"✅ {test_name} passed ({elapsed:.2f}s)")
            self.execution_console.log_output(output)
        else:
            self.execution_console.log_error(f"❌ {test_name} failed")

    def _on_test_summary(self, data: dict) -> None:
        """Handle test summary."""
        summary = data.get("summary", {})
        total = summary.get("total_tests", 0)
        passed = summary.get("passed", 0)
        _ = summary.get("failed", 0)  # noqa: F841
        rate = summary.get("success_rate", 0)

        self.execution_console.log_info(f"Tests: {passed}/{total} passed ({rate:.0f}%)")

    def _on_execution_line(self, data: dict) -> None:
        """Handle execution line output."""
        line = data.get("output") or data.get("line") or ""
        if not line:
            return

        is_error = bool(data.get("is_error")) or data.get("source") in {
            "stderr",
            "error",
        }

        if is_error:
            self.execution_console.log_error(line.rstrip("\n"))
        else:
            # Keep raw formatting for stdout.
            self.execution_console.log_line(line.rstrip("\n"))

    def _on_prompt_detected(self, data: dict) -> None:
        """Handle prompt detected."""
        prompt = data.get("prompt", "")
        if prompt:
            self.execution_console.log_prompt(prompt)

    def _on_input_sent(self, data: dict) -> None:
        """Handle input sent to stdin."""
        input_val = data.get("input", "")
        if input_val:
            self.execution_console.log_input(f'Sending: "{input_val}"')

    def _on_test_output(self, data: dict) -> None:
        """Handle test output."""
        output = data.get("output", "")
        if output:
            self.execution_console.log_output(output)

    def _on_chat_feed_append(self, data: dict) -> None:
        """Append text into the compact chat feed panel."""
        text = data.get("text", "")
        role = data.get("role", "assistant")
        if text:
            try:
                self.test_results.append_chat_text(text, role=role)
            except Exception as e:
                logger.debug(f"Failed to append chat feed text: {e}")

    def _on_chat_feed_clear(self, data: dict) -> None:
        """Clear the chat feed panel."""
        try:
            self.test_results.clear_feed()
        except Exception:
            self.test_results.clear()

    def _on_deployment_started(self, data: dict) -> None:
        """Handle deployment started."""
        self.execution_console.log_info("Deploying program...")
        self.deployment_panel.show_pending()

    def _on_deployment_complete(self, data: dict) -> None:
        """Handle deployment complete."""
        deployment = data.get("deployment", {})
        file_path = deployment.get("file_path", "")
        file_size = deployment.get("file_size", 0)

        test_results = {
            "total": 0,
            "passed": 0,
            "success_rate": 100.0,
        }

        # Get test results from test viewer
        viewer_summary = self.test_results.get_summary()
        test_results.update(viewer_summary)

        self.deployment_panel.show_success(
            file_path=file_path, file_size=file_size, test_results=test_results
        )

        self.execution_console.log_info(f"Deployed: {file_path}")
        self.status_panel.mark_step_complete(7)

    def _on_step_progress(self, data: dict) -> None:
        """Handle step progress update."""
        step = data.get("step", 0)
        _ = data.get("total", 7)  # noqa: F841
        description = data.get("description", "")

        self.status_panel.set_step(step, description)

    def _on_retry_attempt(self, data: dict) -> None:
        """Handle retry attempt."""
        attempt = data.get("attempt", 1)
        max_attempts = data.get("max_attempts", 10)
        _ = data.get("error", "")  # noqa: F841

        self.status_panel.set_attempt(attempt, max_attempts)
        self.execution_console.log_info(f"Retry attempt {attempt}/{max_attempts}")

    def _on_error_occurred(self, data: dict) -> None:
        """Handle error occurred."""
        error = data.get("error", "")
        self.execution_console.log_error(f"Error: {error}")

    # Metasploit event handlers
    def _on_metasploit_command(self, data: dict) -> None:
        """Handle metasploit command execution."""
        command = data.get("command", "")
        if command:
            self.handle_metasploit_command(command)

    def _on_metasploit_output(self, data: dict) -> None:
        """Handle metasploit output."""
        output = data.get("output", "")
        if output and hasattr(self, "terminal_emulator"):
            self.terminal_emulator.append_output(output)

    def _on_session_created(self, data: dict) -> None:
        """Handle session creation."""
        session_id = data.get("session_id", "")
        session_info = data.get("session_info", {})

        if session_id and hasattr(self, "terminal_emulator"):
            self.terminal_emulator.show_session_created(session_id, session_info)

        self.update_sessions({session_id: session_info})

    def _on_listener_started(self, data: dict) -> None:
        """Handle listener start."""
        listener_id = data.get("listener_id", "")
        listener_info = data.get("listener_info", {})

        if listener_id and hasattr(self, "terminal_emulator"):
            self.terminal_emulator.show_listener_started(listener_id, listener_info)

        self.update_listeners({listener_id: listener_info})

    def clear_all(self) -> None:
        """Clear all panels."""
        if self.terminal_mode and hasattr(self, "terminal_emulator"):
            self.terminal_emulator.clear_terminal()
        else:
            if hasattr(self, "code_editor"):
                self.code_editor.clear()
            if hasattr(self, "execution_console"):
                self.execution_console.clear()
            if hasattr(self, "test_results"):
                self.test_results.clear()
            if hasattr(self, "deployment_panel"):
                self.deployment_panel.show_pending()
            if hasattr(self, "status_panel"):
                self.status_panel.reset()
            self.test_id_map.clear()

    def start_timer(self) -> None:
        """Start the elapsed time timer."""
        if hasattr(self, "status_panel"):
            self.status_panel.start_timer()

    def update_timer(self) -> None:
        """Update elapsed time display."""
        if hasattr(self, "status_panel"):
            self.status_panel.update_timer()

    def stop(self) -> None:
        """Stop the sandbox viewer and cleanup."""
        if hasattr(self, "terminal_manager"):
            self.terminal_manager.stop_all()

        self.timer_running = False
        if self.timer_thread:
            self.timer_thread.join(timeout=1.0)

    def configure(self, **kwargs) -> None:
        """
        Configure the frame.

        Args:
            **kwargs: Configuration options
        """
        super().configure(**kwargs)
