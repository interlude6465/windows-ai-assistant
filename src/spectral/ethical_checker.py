"""
Ethical checker module for detecting requests that require authorization/clarification.

Identifies potentially unethical, unauthorized, or dangerous requests that need
clarification before execution.
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class EthicalChecker:
    """
    Detect requests that need authorization/clarification before execution.

    This checker identifies:
    - Unauthorized access attempts (hacking, stealing, etc.)
    - Potentially dangerous operations (malware, backdoors, etc.)
    - Requests that need user authorization confirmation
    - Impossible or unfixable requests
    """

    def __init__(self):
        """Initialize the ethical checker."""
        # Patterns that require authorization check
        self.authorization_patterns = {
            "steal": "Requires authorization - are you authorized to access these credentials?",
            "hack": "Requires authorization - do you have permission to access this system?",
            "crack": "Requires authorization - do you own or have permission to access this?",
            "bypass": "Requires authorization - are you authorized to bypass this security?",
            "exploit": "Requires authorization - do you have permission to test this system?",
        }

        # Patterns that suggest malicious intent (needs purpose clarification)
        self.malicious_patterns = {
            "malware": "Requires clarification - what is the legitimate purpose for this?",
            "backdoor": "Requires clarification - what is the authorized use case?",
            "keylogger": "Requires clarification - do you have authorization for this monitoring?",
            "ransomware": "Refusing - this appears to be illegal activity",
            "botnet": "Refusing - this appears to be illegal activity",
        }

        # Patterns for impossible requests
        self.impossible_patterns = {
            "hack someone else": "Refusing - unauthorized access is illegal",
            "hack the pentagon": "Refusing - unauthorized access is illegal",
            "hack the government": "Refusing - unauthorized access is illegal",
            "someone else's computer": "Refusing - unauthorized access is illegal",
            "someone else's": "Refusing - unauthorized access is illegal",
            "impossible physics": "Refusing - this violates physical laws",
            # Catch "impossible physics code"
            "physics code": "Refusing - this may violate physical laws",
            "violate conservation": "Refusing - violates physics laws",
            "violate thermodynamics": "Refusing - violates physics laws",
            "predict the future": "Refusing - this is scientifically impossible",
            "perpetual motion": "Refusing - this violates thermodynamics",
        }

        logger.info("EthicalChecker initialized")

    def check(self, user_input: str) -> Tuple[bool, str, str]:
        """
        Check if request needs ethical review or clarification.

        Args:
            user_input: User's natural language request

        Returns:
            Tuple of (is_safe, message, category)
            - is_safe: True if safe to proceed, False if needs clarification
            - message: Clarification/refusal message if not safe
            - category: "authorization", "malicious", "impossible", or "safe"
        """
        input_lower = user_input.lower()

        # Check for impossible/unfixable requests first
        for pattern, reason in self.impossible_patterns.items():
            if pattern in input_lower:
                logger.warning(f"Impossible request detected: {pattern}")
                return False, f"⚠️ {reason}", "impossible"

        # Check for authorization-required patterns
        for pattern, reason in self.authorization_patterns.items():
            if pattern in input_lower:
                logger.warning(f"Authorization check needed: {pattern}")
                return False, f"⚠️ {reason}", "authorization"

        # Check for potentially malicious patterns
        for pattern, reason in self.malicious_patterns.items():
            if pattern in input_lower:
                logger.warning(f"Malicious intent check needed: {pattern}")
                return False, f"⚠️ {reason}", "malicious"

        # Passed all checks
        logger.debug("Request passed ethical checks")
        return True, "OK", "safe"

    def is_unfixable(self, request: str, error: str = "") -> bool:
        """
        Determine if error/request is unfixable.

        Args:
            request: Original user request
            error: Error message if any

        Returns:
            True if unfixable (should refuse), False if potentially fixable
        """
        combined = f"{request} {error}".lower()

        # Check impossible patterns
        for pattern in self.impossible_patterns.keys():
            if pattern in combined:
                return True

        # Check for explicit refusals that shouldn't be retried
        refusal_indicators = [
            "illegal",
            "unauthorized",
            "permission denied",
            "access denied",
            "violates",
            "impossible",
        ]

        return any(indicator in combined for indicator in refusal_indicators)
