# agents/optimizer_agent.py
from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
from core.state import CodeFile
from config.prompts import OPTIMIZER_PROMPT


class OptimizerAgent(BaseAgent):
    """Performance optimization specialist"""
    
    def __init__(self):
        super().__init__(agent_name="optimizer")
    
    def get_system_prompt(self) -> str:
        return """You are a performance optimization expert specializing in:
- Algorithm complexity analysis
- Database query optimization
- Memory usage optimization
- Caching strategies
- Async/await patterns
- Resource management

You identify bottlenecks and suggest concrete improvements."""
    
    def get_user_prompt(
        self, 
        code_file: CodeFile, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        context_str = ""
        if context and context.get("profiling_data"):
            context_str += "\n<profiling_data>\n"
            context_str += str(context["profiling_data"])
            context_str += "\n</profiling_data>\n"
        
        return OPTIMIZER_PROMPT.format(
            language=code_file.language,
            file_path=code_file.path,
            code_content=code_file.content,
            context=context_str
        )