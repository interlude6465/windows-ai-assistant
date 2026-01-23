"""Test results viewer panel.

Historically this panel displayed structured automated test results.

For the sandbox UI it now primarily acts as a compact live chat/transcript feed
so users can watch the conversation while generated code executes.

The original test-related methods are still supported so existing event routing
won't break; test events are rendered as simple log lines and summarized.
"""

import logging
import tkinter as tk
from datetime import datetime
from typing import Dict

import customtkinter as ctk

logger = logging.getLogger(__name__)


class TestResultsViewer(ctk.CTkFrame):
    """Compact transcript feed (and optional test event log)."""

    USER_COLOR = "#1E90FF"
    ASSISTANT_COLOR = "#F8F8F2"
    SYSTEM_COLOR = "#8BE9FD"
    ERROR_COLOR = "#FF5555"
    TEST_COLOR = "#F1FA8C"

    def __init__(self, parent_frame, **kwargs):
        super().__init__(parent_frame, **kwargs)

        self.configure(fg_color=("#2B2B2B", "#1E1E1E"))

        # Simple in-memory stats so DeploymentPanel can still show something.
        self._test_stats = {"total": 0, "passed": 0, "failed": 0}
        self._test_counter = 0

        # Title
        self.title_label = ctk.CTkLabel(self, text="💬 CHAT FEED", font=("Arial", 12, "bold"))
        self.title_label.pack(pady=(5, 0), padx=10, anchor="w")

        # Subtitle
        self.summary_label = ctk.CTkLabel(
            self,
            text="Live transcript (8px)",
            font=("Arial", 9),
            text_color="gray",
        )
        self.summary_label.pack(pady=(0, 5), padx=10, anchor="w")

        # Scrollable text area
        self.text_frame = ctk.CTkFrame(self, fg_color=("#1E1E1E", "#111111"))
        self.text_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.scrollbar = ctk.CTkScrollbar(self.text_frame)
        self.scrollbar.pack(side="right", fill="y")

        self.feed_text = tk.Text(
            self.text_frame,
            font=("Consolas", 8),
            foreground=self.ASSISTANT_COLOR,
            background="#1E1E1E",
            insertbackground="white",
            borderwidth=0,
            highlightthickness=0,
            wrap="word",
        )
        self.feed_text.pack(side="left", fill="both", expand=True)
        self.feed_text.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.configure(command=self.feed_text.yview)

        self._configure_tags()

        logger.info("TestResultsViewer (chat feed) initialized")

    def _configure_tags(self) -> None:
        self.feed_text.tag_configure("user", foreground=self.USER_COLOR)
        self.feed_text.tag_configure("assistant", foreground=self.ASSISTANT_COLOR)
        self.feed_text.tag_configure("system", foreground=self.SYSTEM_COLOR)
        self.feed_text.tag_configure("error", foreground=self.ERROR_COLOR)
        self.feed_text.tag_configure("test", foreground=self.TEST_COLOR)
        self.feed_text.tag_configure("timestamp", foreground="#6272A4")

    def _append(self, text: str, tag: str = "assistant", with_timestamp: bool = False) -> None:
        if not text:
            return

        if with_timestamp:
            ts = datetime.now().strftime("%H:%M:%S")
            self.feed_text.insert("end", f"[{ts}] ", "timestamp")

        self.feed_text.insert("end", text, tag)
        self.feed_text.see("end")

        # Keep the widget from growing unbounded.
        max_chars = 200_000
        current_len = int(self.feed_text.index("end-1c").split(".")[0])
        if current_len > 5000:
            # Drop oldest lines.
            self.feed_text.delete("1.0", "200.0")

        if int(self.feed_text.count("1.0", "end", "chars")[0]) > max_chars:
            self.feed_text.delete("1.0", "1000.0")

    # ------------------------------
    # Chat feed API
    # ------------------------------
    def append_chat_text(self, text: str, role: str = "assistant") -> None:
        tag = {
            "user": "user",
            "assistant": "assistant",
            "system": "system",
            "error": "error",
        }.get(role, "assistant")
        self._append(text, tag=tag)

    def clear_feed(self) -> None:
        self.feed_text.delete("1.0", "end")

    # ------------------------------
    # Backwards compatible test API
    # ------------------------------
    def add_test(self, name: str, inputs: list, expected: str) -> str:
        self._test_counter += 1
        self._test_stats["total"] += 1

        test_id = f"test_{self._test_counter}"
        self._append(
            f"\n[Test {self._test_counter}] {name}\n  inputs={inputs}  expected={expected}\n",
            tag="test",
            with_timestamp=True,
        )
        return test_id

    def update_test_running(self, test_id: str) -> None:
        self._append(f"{test_id}: RUNNING\n", tag="test")

    def update_test_passed(self, test_id: str, output: str, elapsed: float) -> None:
        self._test_stats["passed"] += 1
        self._append(f"{test_id}: PASSED ({elapsed:.2f}s) output={output}\n", tag="test")

    def update_test_failed(self, test_id: str, error: str) -> None:
        self._test_stats["failed"] += 1
        self._append(f"{test_id}: FAILED error={error}\n", tag="error")

    def get_summary(self) -> Dict:
        total = self._test_stats["total"]
        passed = self._test_stats["passed"]
        failed = self._test_stats["failed"]

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / total * 100) if total else 0,
        }

    def reset_tests(self) -> None:
        self._test_stats = {"total": 0, "passed": 0, "failed": 0}
        self._test_counter = 0

    def clear(self) -> None:
        self.clear_feed()
        self.reset_tests()

    def configure(self, **kwargs) -> None:  # type: ignore[override]
        super().configure(**kwargs)
