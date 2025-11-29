from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
from core.state import CodeFile
from config.prompts import ANALYZER_PROMPT


class AnalyzerAgent(BaseAgent):
    """
    Specialized agent for detecting bugs, logic errors, and code quality issues
    """
    
    def __init__(self):
        super().__init__(agent_name="analyzer")
    
    def get_system_prompt(self) -> str:
        """System prompt for analyzer agent"""
        return """You are an expert code analyzer with deep knowledge of:
- Common bug patterns across multiple languages
- Edge cases and boundary conditions
- Logic errors and race conditions
- Type safety issues
- Error handling best practices
- Code smells and anti-patterns

You provide actionable, specific feedback with exact line numbers."""
    
    def get_user_prompt(
        self, 
        code_file: CodeFile, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate analyzer-specific prompt"""
        
        # Build context string
        context_str = ""
        if context:
            if context.get("static_analysis"):
                context_str += "\n<static_analysis>\n"
                context_str += "Static analysis tools found:\n"
                for result in context["static_analysis"]:
                    context_str += f"- {result['tool_name']}: {len(result.get('issues', []))} issues\n"
                context_str += "</static_analysis>\n"
            
            if context.get("best_practices"):
                context_str += "\n<best_practices>\n"
                for practice in context["best_practices"]:
                    context_str += f"- {practice.get('title', '')}: {practice.get('content', '')}\n"
                context_str += "</best_practices>\n"
        
        return ANALYZER_PROMPT.format(
            language=code_file.language,
            file_path=code_file.path,
            code_content=code_file.content,
            context=context_str
        )