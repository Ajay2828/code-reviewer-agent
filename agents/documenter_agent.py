# agents/documenter_agent.py
from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
from core.state import CodeFile
from config.prompts import DOCUMENTER_PROMPT


class DocumenterAgent(BaseAgent):
    """Documentation quality specialist"""
    
    def __init__(self):
        super().__init__(agent_name="documenter")
    
    def get_system_prompt(self) -> str:
        return """You are a documentation quality expert focusing on:
- Function and class documentation
- API documentation
- Inline comments quality
- Type hints and annotations
- README and usage examples
- Code readability

You ensure code is well-documented and maintainable."""
    
    def get_user_prompt(
        self, 
        code_file: CodeFile, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        context_str = ""
        if context and context.get("existing_docs"):
            context_str += "\n<existing_documentation>\n"
            context_str += context["existing_docs"]
            context_str += "\n</existing_documentation>\n"
        
        return DOCUMENTER_PROMPT.format(
            language=code_file.language,
            file_path=code_file.path,
            code_content=code_file.content,
            context=context_str
        )