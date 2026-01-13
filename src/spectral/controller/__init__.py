"""
Controller package for the dual-model stack.

Provides planning (brain) and execution (dispatch) capabilities for routing
user intents through BrainServer and ExecutorServer.
"""

from spectral.controller.brain_server import BrainServer
from spectral.controller.controller import Controller, ControllerResult
from spectral.controller.dispatcher import Dispatcher, StepOutcome
from spectral.controller.executor_server import ExecutorServer
from spectral.controller.planner import Planner

__all__ = [
    "BrainServer",
    "Controller",
    "ControllerResult",
    "Dispatcher",
    "ExecutorServer",
    "Planner",
    "StepOutcome",
]
