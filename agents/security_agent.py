from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
from core.state import CodeFile
from config.prompts import SECURITY_PROMPT


class SecurityAgent(BaseAgent):
    """
    Specialized agent for detecting security vulnerabilities
    
    Focuses on OWASP Top 10 and common CVEs
    """
    
    def __init__(self):
        super().__init__(agent_name="security")
    
    def get_system_prompt(self) -> str:
        """System prompt for security agent"""
        return """You are a security expert specializing in:
- OWASP Top 10 vulnerabilities
- SQL injection, XSS, CSRF
- Authentication and authorization flaws
- Insecure data handling
- Cryptographic issues
- Dependency vulnerabilities
- Input validation
- Security misconfigurations

You think like an attacker to find exploitable vulnerabilities."""
    
    def get_user_prompt(
        self, 
        code_file: CodeFile, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate security-specific prompt"""
        
        context_str = ""
        if context:
            # Include known CVEs or security patterns
            if context.get("known_vulnerabilities"):
                context_str += "\n<known_vulnerabilities>\n"
                for vuln in context["known_vulnerabilities"]:
                    context_str += f"- {vuln}\n"
                context_str += "</known_vulnerabilities>\n"
            
            # Include dependency information
            if context.get("dependencies"):
                context_str += "\n<dependencies>\n"
                context_str += "Dependencies in use:\n"
                for dep in context["dependencies"]:
                    context_str += f"- {dep}\n"
                context_str += "</dependencies>\n"
        
        return SECURITY_PROMPT.format(
            language=code_file.language,
            file_path=code_file.path,
            code_content=code_file.content,
            context=context_str
        )