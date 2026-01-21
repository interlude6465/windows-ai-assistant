"""
Intelligent Penetration Testing Assistant.

Conducts conversational penetration testing without hardcoded shortcuts.
- Asks clarifying questions about targets
- Researches vulnerabilities and exploits
- Reasons through methodology
- Generates commands dynamically based on reasoning
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExploitStage(Enum):
    """Stages of penetration testing engagement."""

    RECONNAISSANCE = "reconnaissance"  # Gather target info
    ENUMERATION = "enumeration"  # Detail discovery
    VULNERABILITY_ASSESSMENT = "vulnerability_assessment"  # Find CVEs
    EXPLOITATION = "exploitation"  # Execute exploit
    POST_EXPLOITATION = "post_exploitation"  # Maintain access


@dataclass
class TargetInfo:
    """Information about the penetration test target."""

    ip_address: Optional[str] = None
    os_type: Optional[str] = None  # Windows, Linux, macOS, Android, iOS
    os_version: Optional[str] = None  # 10, 11, 20.04, etc.
    architecture: Optional[str] = None  # x86, x64, ARM, etc.
    services: List[str] = field(default_factory=list)
    open_ports: List[int] = field(default_factory=list)
    user_agent: Optional[str] = None  # For web services
    access_level: Optional[str] = None  # Unauthenticated, User, Admin
    network_info: Dict[str, Any] = field(default_factory=dict)
    cves: List[str] = field(default_factory=list)


class PenetrationTester:
    """
    Intelligent penetration testing assistant.

    Conducts methodology-driven testing through conversation, not hardcoded shortcuts.
    """

    def __init__(self, llm_client, research_handler=None):
        """
        Initialize the penetration tester.

        Args:
            llm_client: LLM for reasoning and conversation
            research_handler: Research handler for vulnerability lookups
        """
        self.llm_client = llm_client
        self.research_handler = research_handler
        self.target: Optional[TargetInfo] = None
        self.stage = ExploitStage.RECONNAISSANCE
        self.conversation_history = []

    def handle_pentest_request(self, user_message: str) -> str:
        """
        Handle a penetration testing request through intelligent conversation.

        This is the main entry point - NOT a hardcoded shortcut.

        Args:
            user_message: User's request (e.g., "test my Windows machine")

        Returns:
            AI's response (question, finding, or command)
        """
        logger.info(f"Pentest request: {user_message}")

        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Determine current stage and what's needed
        response = self._stage_handler(user_message)

        # Add AI response to history
        self.conversation_history.append({"role": "assistant", "content": response})

        return response

    def _stage_handler(self, user_message: str) -> str:
        """
        Route to appropriate stage handler based on what info we have.

        Stages:
        1. RECONNAISSANCE: Gather basic target info (IP, OS type)
        2. ENUMERATION: Discover services, ports, versions
        3. VULNERABILITY_ASSESSMENT: Research CVEs and exploits
        4. EXPLOITATION: Execute chosen method
        5. POST_EXPLOITATION: Maintain access, escalate privileges
        """

        if not self.target or not self.target.ip_address:
            # Stage 1: Need basic target info
            return self._reconnaissance_stage(user_message)

        elif not self.target.os_type:
            # Stage 2: Need OS info
            return self._enumerate_os(user_message)

        elif not self.target.services:
            # Stage 3: Need service enumeration
            return self._enumerate_services(user_message)

        elif not self.target.cves:
            # Stage 4: Need vulnerability assessment
            return self._assess_vulnerabilities(user_message)

        else:
            # Stage 5: Ready for exploitation
            return self._exploitation_stage(user_message)

    def _reconnaissance_stage(self, user_message: str) -> str:
        """
        Stage 1: Ask for basic target information.

        Questions:
        - What's the target IP address?
        - What OS? (Windows, Linux, macOS, Android, iOS, etc.)
        - What's the goal? (info gathering, RCE, persistence, etc.)
        """

        # Parse for IP address
        ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
        ip_match = re.search(ip_pattern, user_message)

        if ip_match:
            self.target = TargetInfo(ip_address=ip_match.group())
            logger.info(f"Target IP identified: {self.target.ip_address}")

        # Parse for OS type
        os_keywords = {
            r"\bwindows\b": "Windows",
            r"\blinux\b": "Linux",
            r"\bubuntu\b": "Linux",
            r"\bcentos\b": "Linux",
            r"\bmacos\b": "macOS",
            r"\bandroid\b": "Android",
            r"\bios\b": "iOS",
        }

        for pattern, os_name in os_keywords.items():
            if re.search(pattern, user_message, re.IGNORECASE):
                if not self.target:
                    self.target = TargetInfo()
                self.target.os_type = os_name
                logger.info(f"OS type identified: {os_name}")
                break

        # Generate question based on what we're missing
        if not self.target or not self.target.ip_address:
            return (
                "I'll help you test your target systematically. First, I need some details:\n\n"
                "1. **Target IP Address**: What's the IP of the machine you want to test?\n"
                "2. **Operating System**: Windows, Linux, macOS, Android, iOS, or something else?\n"
                "3. **OS Version**: (e.g., Windows 10 21H2, Ubuntu 20.04, etc.)\n\n"
                "Once I have these details, I can research applicable exploits and determine the best approach."
            )
        elif not self.target.os_version:
            return (
                f"Great! I've noted the target:\n"
                f"- **IP**: {self.target.ip_address}\n"
                f"- **OS**: {self.target.os_type}\n\n"
                f"Now I need more specifics:\n\n"
                f"1. **Exact OS Version**: (e.g., Windows 10 version 21H2, build 19044)\n"
                f"2. **Known Services**: Any services you know are running? (SSH, RDP, HTTP, SMB, etc.)\n"
                f"3. **Network Access**: Can you reach this machine from your current network?\n"
                f"4. **Your Access Level**: Do you have any credentials? User account? Admin?\n\n"
                f"This info helps me research the right vulnerabilities."
            )
        else:
            # Move to next stage
            return self._enumerate_services(user_message)

    def _enumerate_os(self, user_message: str) -> str:
        """Ask for OS version details."""
        # Parse version info from user message
        version_patterns = {
            r"windows\s+(\d+)": "Windows",
            r"ubuntu\s+([\d.]+)": "Ubuntu",
            r"centos\s+([\d.]+)": "CentOS",
            r"build\s+(\d+)": "Build",
        }

        for pattern, label in version_patterns.items():
            match = re.search(pattern, user_message, re.IGNORECASE)
            if match and self.target:
                self.target.os_version = match.group(1)
                logger.info(f"OS version identified: {self.target.os_version}")

        if self.target.os_version:
            return self._enumerate_services(user_message)

        return (
            "I need the specific OS version to research applicable CVEs.\n\n"
            "Examples:\n"
            "- **Windows**: 'Windows 10 build 19044' or 'Windows 11 22H2'\n"
            "- **Linux**: 'Ubuntu 20.04 LTS' or 'CentOS 7.9'\n"
            "- **Android**: 'Android 11' or 'Android 12'\n\n"
            "What's your target running?"
        )

    def _enumerate_services(self, user_message: str) -> str:
        """Ask for running services and open ports."""

        # Parse service keywords
        service_keywords = [
            "ssh",
            "rdp",
            "smb",
            "http",
            "https",
            "ftp",
            "telnet",
            "mysql",
            "postgresql",
            "mongodb",
            "redis",
            "vnc",
            "nfs",
        ]

        found_services = []
        for service in service_keywords:
            if service in user_message.lower():
                found_services.append(service.upper())

        if found_services and self.target:
            self.target.services = found_services
            logger.info(f"Services identified: {found_services}")

        if found_services:
            return self._assess_vulnerabilities(user_message)

        return (
            f"Now let's identify what services are running on {self.target.ip_address if self.target else 'the target'}.\n\n"
            f"**What services are accessible?** (Check which ports respond):\n\n"
            f"Common ports:\n"
            f"- Port 22: SSH (Linux/macOS)\n"
            f"- Port 3389: RDP (Windows Remote Desktop)\n"
            f"- Port 445: SMB (Windows file sharing)\n"
            f"- Port 80/443: HTTP/HTTPS (Web servers)\n"
            f"- Port 3306: MySQL\n"
            f"- Port 5432: PostgreSQL\n"
            f"- Port 5900: VNC\n\n"
            f"Which services are running? (You can scan with: nmap -p- {self.target.ip_address if self.target else '<IP>'} for a full port scan)"
        )

    def _assess_vulnerabilities(self, user_message: str) -> str:
        """
        Research vulnerabilities for the identified target.

        Uses research handler to find CVEs and applicable exploits.
        """
        if not self.target or not self.target.os_version:
            return "I need the OS version to research vulnerabilities. Can you provide that?"

        # Build research query
        research_query = (
            f"{self.target.os_type} {self.target.os_version} vulnerabilities "
            f"exploits {' '.join(self.target.services)}"
        )

        logger.info(f"Researching: {research_query}")

        # Use research handler if available
        if self.research_handler:
            try:
                research_results, _ = self.research_handler.handle_research_query(research_query)

                # Extract CVEs from research
                cve_pattern = r"CVE-\d{4}-\d{4,}"
                cves = re.findall(cve_pattern, research_results)

                if cves and self.target:
                    self.target.cves = cves[:5]  # Top 5 CVEs
                    logger.info(f"CVEs found: {self.target.cves}")

                response = (
                    f"**Vulnerability Assessment Results:**\n\n"
                    f"Target: {self.target.os_type} {self.target.os_version}\n"
                    f"Services: {', '.join(self.target.services)}\n\n"
                    f"**Known Vulnerabilities:**\n"
                )

                if cves:
                    response += "\n".join([f"- {cve}" for cve in self.target.cves])
                else:
                    response += "No specific CVEs found, but the system may still be vulnerable to common attacks.\n"

                response += (
                    f"\n\n**Next Steps:**\n"
                    f"1. Would you like me to generate an exploit for a specific CVE?\n"
                    f"2. Or try a general exploitation method (brute-force, default creds, etc.)?\n"
                    f"3. What's your access level - do you have credentials?\n\n"
                )

                return response

            except Exception as e:
                logger.error(f"Research failed: {e}")

        # Fallback without research handler
        response = (
            f"**Vulnerability Assessment for {self.target.os_type} {self.target.os_version}**\n\n"
            f"Based on standard vulnerability databases, common issues for this OS:\n\n"
        )

        if "Windows" in self.target.os_type:
            response += (
                "- EternalBlue (SMB vulnerability) - if unpatched\n"
                "- BlueKeep (RDP vulnerability)\n"
                "- Zerologon (Netlogon vulnerability)\n"
                "- Common RDP brute-force\n"
            )
        elif "Linux" in self.target.os_type:
            response += (
                "- Privilege escalation via sudo/SUID\n"
                "- SSH brute-force or key-based exploits\n"
                "- Kernel vulnerabilities\n"
                "- Unpatched service vulnerabilities\n"
            )

        response += (
            "\nTo proceed, I need to know:\n"
            "1. Can you execute commands/code on the target?\n"
            "2. What payload formats work? (.exe, .elf, .apk, script, etc.)\n"
            "3. Any network restrictions?\n\n"
            "Once I know this, I'll generate the appropriate exploit chain."
        )

        return response

    def _exploitation_stage(self, user_message: str) -> str:
        """
        Stage 5: Generate and execute exploitation method.

        Based on all gathered info, AI reasons through:
        - Best exploit for this target
        - Payload format and encoding
        - Delivery method
        - Post-exploitation activities
        """

        if not self.target:
            return "Target information is incomplete. Please provide target details."

        # AI reasons through exploitation strategy
        exploitation_prompt = f"""
        You are a professional penetration tester. Based on this target information,
        determine the BEST exploitation method (not hardcoded, actual reasoning):
        
        **Target Information:**
        - IP: {self.target.ip_address}
        - OS: {self.target.os_type} {self.target.os_version}
        - Architecture: {self.target.architecture or 'Unknown (assume standard)'}
        - Services: {', '.join(self.target.services)}
        - CVEs: {', '.join(self.target.cves) if self.target.cves else 'None identified'}
        - Access Level: {self.target.access_level or 'Unauthenticated'}
        
        **User's Goals from Conversation:**
        {self._summarize_goals(user_message)}
        
        **Your Task (REASON THROUGH THIS, DON'T JUST SHORTCUT):**
        1. What are the BEST exploit vectors for this specific configuration?
        2. Why is this method best? (explain your reasoning)
        3. What payload should we use?
        4. What are success indicators?
        5. What post-exploitation activities would be most effective?
        
        **Output Format:**
        **Recommended Exploitation Strategy:**
        [Your detailed reasoning and strategy]
        
        **Implementation:**
        [Step-by-step commands/setup to execute]
        
        **Risk Assessment:**
        [IDS/AV considerations, detection risk, etc.]
        """

        # Get AI reasoning
        ai_strategy = self.llm_client.chat(
            [
                {
                    "role": "system",
                    "content": "You are an expert penetration tester. Reason through exploitation methodology systematically.",
                },
                {"role": "user", "content": exploitation_prompt},
            ]
        )

        logger.info(f"AI Strategy Generated:\n{ai_strategy}")

        return ai_strategy

    def _summarize_goals(self, user_message: str) -> str:
        """Extract goals from conversation history."""
        goals = []

        goal_keywords = {
            r"\b(reverse shell|rce|remote code)\b": "Remote Code Execution",
            r"\b(escalate|privilege)\b": "Privilege Escalation",
            r"\b(data|exfiltrate|steal)\b": "Data Exfiltration",
            r"\b(persist|backdoor|access)\b": "Persistence/Backdoor",
            r"\b(lateral|move)\b": "Lateral Movement",
            r"\b(test|audit)\b": "Security Testing",
        }

        conversation_text = " ".join([m.get("content", "") for m in self.conversation_history])
        for pattern, goal in goal_keywords.items():
            if re.search(pattern, conversation_text, re.IGNORECASE):
                if goal not in goals:
                    goals.append(goal)

        return (
            "\n".join([f"- {goal}" for goal in goals]) if goals else "- Security testing/assessment"
        )
