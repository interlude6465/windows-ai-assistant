"""
Terminal Emulator - Live terminal display for metasploit execution.

Features:
- Real-time command/output streaming
- Black background, green text (hacker aesthetic)
- Session visualization
- Command history
- Session management interface
"""

import logging
import queue
import threading
import time
from tkinter import END, Scrollbar, Text
from tkinter.scrolledtext import ScrolledText
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

logger = logging.getLogger(__name__)


class TerminalEmulator(ctk.CTkFrame):
    """
    Live terminal emulator for metasploit output.

    Features:
    - Black background, green text
    - Real-time streaming of output
    - Command history display
    - Session status visualization
    - Multiple listener display
    """

    def __init__(self, parent_frame, **kwargs):
        """
        Initialize the terminal emulator.

        Args:
            parent_frame: Parent frame to pack into
            **kwargs: Additional frame arguments
        """
        super().__init__(parent_frame, **kwargs)

        self.configure(fg_color="#000000")

        # Terminal output buffer
        self.output_queue = queue.Queue()
        self.output_thread = None
        self.output_running = False

        # Terminal state
        self.command_history = []
        self.current_command = ""
        self.active_sessions = {}
        self.active_listeners = {}

        # UI components
        self._setup_ui()

        # Start output processing thread
        self._start_output_processor()

        logger.info("TerminalEmulator initialized")

    def _setup_ui(self) -> None:
        """Set up the terminal UI components."""

        # Header with session/listener info
        self.header_frame = ctk.CTkFrame(self, fg_color="#111111", height=40)
        self.header_frame.pack(fill="x", padx=5, pady=(5, 0))
        self.header_frame.pack_propagate(False)

        # Session status label
        self.sessions_label = ctk.CTkLabel(
            self.header_frame,
            text="Sessions: None | Listeners: None",
            font=("Consolas", 10),
            text_color="#00ff00",
            anchor="w",
        )
        self.sessions_label.pack(side="left", padx=10, pady=5)

        # Clear button
        self.clear_button = ctk.CTkButton(
            self.header_frame,
            text="Clear",
            width=60,
            height=25,
            font=("Consolas", 9),
            fg_color="#333333",
            hover_color="#555555",
            command=self.clear_terminal,
        )
        self.clear_button.pack(side="right", padx=10, pady=5)

        # Main terminal area
        self.terminal_frame = ctk.CTkFrame(self, fg_color="#000000")
        self.terminal_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Terminal text widget with black background and green text
        self.terminal_text = Text(
            self.terminal_frame,
            bg="#000000",
            fg="#00ff00",
            font=("Consolas", 10),
            insertbackground="#00ff00",
            selectbackground="#003300",
            relief="flat",
            wrap="word",
            state="disabled",
        )

        # Scrollbar for terminal
        self.scrollbar = Scrollbar(
            self.terminal_frame, orient="vertical", command=self.terminal_text.yview
        )
        self.terminal_text.configure(yscrollcommand=self.scrollbar.set)

        # Pack terminal components
        self.terminal_text.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Bind mouse wheel scrolling
        self._bind_scroll_events()

        # Command input area
        self.input_frame = ctk.CTkFrame(self, fg_color="#111111", height=30)
        self.input_frame.pack(fill="x", padx=5, pady=(0, 5))
        self.input_frame.pack_propagate(False)

        # Command prompt
        self.prompt_label = ctk.CTkLabel(
            self.input_frame,
            text="msf6> ",
            font=("Consolas", 10, "bold"),
            text_color="#00ff00",
            anchor="w",
        )
        self.prompt_label.pack(side="left", padx=5, pady=5)

        # Command entry (read-only for now, but designed for future interaction)
        self.command_entry = ctk.CTkEntry(
            self.input_frame,
            font=("Consolas", 10),
            fg_color="#000000",
            text_color="#00ff00",
            border_color="#333333",
            placeholder_text_color="#006600",
            state="disabled",  # Disabled for now, could be enabled for interactive commands
        )
        self.command_entry.pack(side="left", fill="x", expand=True, padx=(0, 5), pady=5)

    def _bind_scroll_events(self) -> None:
        """Bind mouse wheel scrolling events."""

        def _on_mousewheel(event):
            self.terminal_text.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_to_mousewheel(event):
            self.terminal_text.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_from_mousewheel(event):
            self.terminal_text.unbind_all("<MouseWheel>")

        # Bind scrolling when mouse enters/leaves the terminal
        self.terminal_text.bind("<Enter>", _bind_to_mousewheel)
        self.terminal_text.bind("<Leave>", _unbind_from_mousewheel)

    def _start_output_processor(self) -> None:
        """Start the output processing thread."""
        self.output_running = True
        self.output_thread = threading.Thread(
            target=self._process_output_queue, daemon=True
        )
        self.output_thread.start()

    def _process_output_queue(self) -> None:
        """Process output queue in a separate thread."""
        while self.output_running:
            try:
                # Get output from queue with timeout
                output_line = self.output_queue.get(timeout=0.1)
                self._display_output(output_line)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing output queue: {e}")

    def _display_output(self, output_line: str) -> None:
        """Display output in the terminal."""

        def update_terminal():
            self.terminal_text.configure(state="normal")

            # Add timestamp for new commands
            if output_line.startswith("msf6>") or output_line.startswith("[*]"):
                timestamp = time.strftime("%H:%M:%S")
                self.terminal_text.insert(END, f"[{timestamp}] {output_line}\n")
            else:
                self.terminal_text.insert(END, f"{output_line}\n")

            # Auto-scroll to bottom
            self.terminal_text.see(END)
            self.terminal_text.configure(state="disabled")

        # Schedule update in main thread
        self.after(0, update_terminal)

    def append_output(self, text: str) -> None:
        """
        Append text to the terminal output.

        Args:
            text: Text to append
        """
        # Strip ANSI escape sequences for display
        clean_text = self._strip_ansi_codes(text)

        # Add to output queue
        try:
            self.output_queue.put_nowait(clean_text)
        except queue.Full:
            # If queue is full, skip this output
            logger.warning("Output queue full, skipping output")

    def _strip_ansi_codes(self, text: str) -> str:
        """Strip ANSI escape sequences from text."""
        import re

        # Remove ANSI escape sequences
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    def show_command(self, command: str) -> None:
        """
        Display a command in the terminal.

        Args:
            command: Command to display
        """
        self.command_history.append(command)
        self.append_output(f"msf6> {command}")

    def update_sessions(self, sessions: Dict[str, Dict]) -> None:
        """
        Update active sessions display.

        Args:
            sessions: Dictionary of active sessions
        """
        self.active_sessions = sessions
        self._update_status_display()

    def update_listeners(self, listeners: Dict[str, Dict]) -> None:
        """
        Update active listeners display.

        Args:
            listeners: Dictionary of active listeners
        """
        self.active_listeners = listeners
        self._update_status_display()

    def _update_status_display(self) -> None:
        """Update the status display in the header."""
        sessions_count = len(self.active_sessions)
        listeners_count = len(self.active_listeners)

        status_text = f"Sessions: {sessions_count} | Listeners: {listeners_count}"

        # Add session details if any exist
        if sessions_count > 0:
            session_details = []
            for session_id, session in self.active_sessions.items():
                details = f"S{session_id}:{session.get('type', 'unknown')}"
                session_details.append(details)
            status_text += f" ({', '.join(session_details)})"

        # Add listener details if any exist
        if listeners_count > 0:
            listener_details = []
            for listener_id, listener in self.active_listeners.items():
                details = f"{listener.get('payload', 'unknown')}@{listener.get('lport', 'unknown')}"
                listener_details.append(details)
            status_text += f" | L: ({', '.join(listener_details)})"

        def update_label():
            self.sessions_label.configure(text=status_text)

        self.after(0, update_label)

    def clear_terminal(self) -> None:
        """Clear the terminal output."""

        def clear_output():
            self.terminal_text.configure(state="normal")
            self.terminal_text.delete(1.0, END)
            self.terminal_text.configure(state="disabled")

        self.after(0, clear_output)

    def show_session_created(self, session_id: str, session_info: Dict) -> None:
        """
        Show session creation notification.

        Args:
            session_id: ID of the created session
            session_info: Session information dictionary
        """
        timestamp = time.strftime("%H:%M:%S")
        notification = f"[{timestamp}] [*] Session {session_id} opened: {session_info.get('description', 'Unknown session')}"
        self.append_output(notification)

    def show_listener_started(self, listener_id: str, listener_info: Dict) -> None:
        """
        Show listener start notification.

        Args:
            listener_id: ID of the started listener
            listener_info: Listener information dictionary
        """
        timestamp = time.strftime("%H:%M:%S")
        lhost = listener_info.get("lhost", "0.0.0.0")
        lport = listener_info.get("lport", "unknown")
        payload = listener_info.get("payload", "unknown")
        notification = f"[{timestamp}] [*] Started {payload} handler on {lhost}:{lport}"
        self.append_output(notification)

    def enable_interactive_mode(self) -> None:
        """Enable interactive command mode."""
        self.command_entry.configure(state="normal")

    def disable_interactive_mode(self) -> None:
        """Disable interactive command mode."""
        self.command_entry.configure(state="disabled")

    def stop(self) -> None:
        """Stop the terminal emulator."""
        self.output_running = False
        if self.output_thread:
            self.output_thread.join(timeout=1.0)
        logger.info("TerminalEmulator stopped")

    def get_terminal_height(self) -> int:
        """Get the current terminal height in lines."""
        return int(self.terminal_text.index("end-1c").split(".")[0])

    def save_output(self, filename: str) -> bool:
        """
        Save terminal output to a file.

        Args:
            filename: Filename to save to

        Returns:
            True if successful
        """
        try:
            with open(filename, "w") as f:
                content = self.terminal_text.get(1.0, END)
                f.write(content)
            logger.info(f"Terminal output saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save terminal output: {e}")
            return False


class TerminalManager:
    """
    Manager for multiple terminal instances.

    Useful for managing multiple metasploit sessions or different terminal contexts.
    """

    def __init__(self):
        """Initialize the terminal manager."""
        self.terminals = {}
        self.current_terminal_id = "default"

        logger.info("TerminalManager initialized")

    def create_terminal(
        self, terminal_id: str, parent_frame, **kwargs
    ) -> TerminalEmulator:
        """
        Create a new terminal instance.

        Args:
            terminal_id: Unique identifier for the terminal
            parent_frame: Parent frame for the terminal
            **kwargs: Additional arguments for TerminalEmulator

        Returns:
            Created TerminalEmulator instance
        """
        if terminal_id in self.terminals:
            logger.warning(f"Terminal {terminal_id} already exists")
            return self.terminals[terminal_id]

        terminal = TerminalEmulator(parent_frame, **kwargs)
        self.terminals[terminal_id] = terminal

        logger.info(f"Created terminal {terminal_id}")
        return terminal

    def get_terminal(self, terminal_id: str = None) -> Optional[TerminalEmulator]:
        """
        Get a terminal instance.

        Args:
            terminal_id: Terminal ID (defaults to current)

        Returns:
            TerminalEmulator instance or None
        """
        if terminal_id is None:
            terminal_id = self.current_terminal_id

        return self.terminals.get(terminal_id)

    def set_current_terminal(self, terminal_id: str) -> bool:
        """
        Set the current active terminal.

        Args:
            terminal_id: ID of terminal to set as current

        Returns:
            True if successful
        """
        if terminal_id in self.terminals:
            self.current_terminal_id = terminal_id
            logger.info(f"Set current terminal to {terminal_id}")
            return True
        else:
            logger.error(f"Terminal {terminal_id} does not exist")
            return False

    def remove_terminal(self, terminal_id: str) -> bool:
        """
        Remove a terminal instance.

        Args:
            terminal_id: ID of terminal to remove

        Returns:
            True if successful
        """
        if terminal_id in self.terminals:
            terminal = self.terminals[terminal_id]
            terminal.stop()
            del self.terminals[terminal_id]

            # If this was the current terminal, switch to default
            if terminal_id == self.current_terminal_id:
                self.current_terminal_id = "default"

            logger.info(f"Removed terminal {terminal_id}")
            return True
        else:
            logger.error(f"Terminal {terminal_id} does not exist")
            return False

    def stop_all(self) -> None:
        """Stop all terminal instances."""
        for terminal in self.terminals.values():
            terminal.stop()
        self.terminals.clear()
        logger.info("All terminals stopped")
