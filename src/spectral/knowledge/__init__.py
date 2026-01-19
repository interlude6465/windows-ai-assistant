"""Knowledge base modules for specialized domain expertise."""

from spectral.knowledge.metasploit_guide import (
    METASPLOIT_KNOWLEDGE,
    get_auto_fix_command,
    diagnose_error,
    get_exploit_recommendations,
    get_payload_recommendations,
)

__all__ = [
    "METASPLOIT_KNOWLEDGE",
    "get_auto_fix_command",
    "diagnose_error",
    "get_exploit_recommendations",
    "get_payload_recommendations",
]
