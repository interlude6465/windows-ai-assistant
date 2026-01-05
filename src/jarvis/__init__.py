"""
Jarvis: Advanced Windows AI Assistant with local LLM support
"""

__version__ = "0.1.0"

# Export main components for external use
from jarvis.action_executor import ActionExecutor, ActionResult
from jarvis.app import GUIApp, create_gui_app
from jarvis.brain.server import BrainServer, BrainServerError
from jarvis.chat import ChatMessage, ChatSession
from jarvis.code_cleaner import CodeCleaner
from jarvis.config import (
    JarvisConfig,
    LLMConfig,
    SafetyConfig,
    StorageConfig,
    ExecutionConfig,
    OCRConfig,
)
from jarvis.container import Container
from jarvis.conversation_context import ConversationContext, ConversationTurn
from jarvis.execution_debugger import ExecutionDebugger
from jarvis.interactive_executor import InteractiveExecutor
from jarvis.interactive_program_analyzer import InteractiveProgramAnalyzer, ProgramType
from jarvis.mistake_learner import LearningPattern, MistakeLearner
from jarvis.output_validator import OutputValidator
from jarvis.program_deployer import ProgramDeployer
from jarvis.sandbox_execution_system import SandboxExecutionSystem
from jarvis.sandbox_manager import SandboxManager, SandboxState, SandboxInfo
from jarvis.test_case_generator import TestCaseGenerator
from jarvis.config import (
    BrainLLMConfig,
    DualLLMConfig,
    ExecutorLLMConfig,
    JarvisConfig,
    LLMConfig,
    SafetyConfig,
    StorageConfig,
)
from jarvis.container import Container, DualModelManager
from jarvis.executor.server import ExecutorServer, ExecutorServerError
from jarvis.llm_client import LLMClient, LLMConnectionError
from jarvis.memory_rag.rag_service import DocumentChunk, RAGMemoryService, RetrievalResult
from jarvis.orchestrator import Orchestrator
from jarvis.reasoning import Plan, PlanStep, ReasoningModule, SafetyFlag, StepStatus
from jarvis.system_actions import SystemActionRouter
from jarvis.tool_teaching import ToolTeachingModule
from jarvis.voice import VoiceInterface

__all__ = [
    "ActionExecutor",
    "ActionResult",
    "BrainLLMConfig",
    "BrainServer",
    "BrainServerError",
    "ChatMessage",
    "ChatSession",
    "CodeCleaner",
    "ConversationContext",
    "ConversationTurn",
    "Container",
    "ExecutionConfig",
    "ExecutionDebugger",
    "create_gui_app",
    "GUIApp",
    "DocumentChunk",
    "DualLLMConfig",
    "DualModelManager",
    "ExecutorLLMConfig",
    "ExecutorServer",
    "ExecutorServerError",
    "Controller",
    "ControllerResult",
    "Dispatcher",
    "InteractiveExecutor",
    "InteractiveProgramAnalyzer",
    "JarvisConfig",
    "LLMClient",
    "LLMConfig",
    "LLMConnectionError",
    "LearningPattern",
    "MistakeLearner",
    "OCRConfig",
    "Orchestrator",
    "OutputValidator",
    "Plan",
    "PlanStep",
    "ProgramDeployer",
    "ProgramType",
    "RAGMemoryService",
    "ReasoningModule",
    "RetrievalResult",
    "SafetyConfig",
    "SandboxExecutionSystem",
    "SandboxInfo",
    "SandboxManager",
    "SandboxState",
    "SafetyFlag",
    "StepOutcome",
    "StepStatus",
    "StorageConfig",
    "SystemActionRouter",
    "TestCaseGenerator",
    "ToolTeachingModule",
    "VoiceInterface",
]
