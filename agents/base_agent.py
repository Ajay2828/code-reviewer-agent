import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import structlog

from core.llm_manager import get_llm_manager
from core.state import CodeFile, Issue, AgentResult
from config.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()


class BaseAgent(ABC):
    """
    Base class for all specialized agents
    
    Provides common functionality:
    - LLM interaction
    - Output parsing
    - Error handling
    - Self-reflection
    """
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.llm_manager = get_llm_manager()
        
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent"""
        pass
    
    @abstractmethod
    def get_user_prompt(
        self, 
        code_file: CodeFile, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate user prompt with code and context"""
        pass
    
    async def analyze(
        self, 
        code_file: CodeFile, 
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Main analysis method
        
        Args:
            code_file: Code file to analyze
            context: Additional context (RAG results, static analysis, etc.)
        
        Returns:
            AgentResult with issues found
        """
        start_time = time.time()
        
        try:
            logger.info(
                f"{self.agent_name}_analysis_started",
                file=code_file.path,
                language=code_file.language
            )
            
            # Build prompts
            system_prompt = self.get_system_prompt()
            user_prompt = self.get_user_prompt(code_file, context)
            
            # Generate response
            response = await self.llm_manager.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse response
            issues = self._parse_response(response["content"])
            
            # Self-reflection if enabled
            if settings.ENABLE_SELF_REFLECTION:
                issues = await self._self_reflect(
                    code_file, 
                    issues, 
                    response["content"]
                )
            
            # Filter by confidence threshold
            issues = [
                issue for issue in issues 
                if issue.confidence >= settings.CONFIDENCE_THRESHOLD
            ]
            
            execution_time = time.time() - start_time
            
            logger.info(
                f"{self.agent_name}_analysis_complete",
                issues_found=len(issues),
                execution_time=execution_time,
                cost=response["cost"]
            )
            
            return AgentResult(
                agent_name=self.agent_name,
                issues=issues,
                reasoning=self._extract_reasoning(response["content"]),
                score=self._extract_score(response["content"]),
                execution_time=execution_time,
                cost=response["cost"],
                success=True
            )
            
        except Exception as e:
            logger.error(
                f"{self.agent_name}_analysis_failed",
                error=str(e),
                file=code_file.path
            )
            
            return AgentResult(
                agent_name=self.agent_name,
                issues=[],
                reasoning="",
                execution_time=time.time() - start_time,
                success=False,
                error=str(e)
            )
    
    def _parse_response(self, content: str) -> List[Issue]:
        """
        Parse LLM response into structured issues
        
        Expected JSON format:
        {
            "reasoning": "...",
            "issues": [...],
            "score": 85
        }
        """
        try:
            # Try to extract JSON from response
            content = content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            data = json.loads(content)
            
            issues = []
            for idx, issue_data in enumerate(data.get("issues", [])):
                issue = Issue(
                    id=f"{self.agent_name}_{idx}",
                    severity=issue_data.get("severity", "minor"),
                    category=issue_data.get("category", "style"),
                    line_start=issue_data.get("line_start", 0),
                    line_end=issue_data.get("line_end"),
                    title=issue_data.get("title", "Issue found"),
                    description=issue_data.get("description", ""),
                    suggestion=issue_data.get("suggestion", ""),
                    suggested_code=issue_data.get("suggested_code"),
                    confidence=issue_data.get("confidence", 0.8),
                    sources=[self.agent_name],
                    cwe_id=issue_data.get("cwe_id"),
                    impact=issue_data.get("impact")
                )
                issues.append(issue)
            
            return issues
            
        except json.JSONDecodeError as e:
            logger.error(
                f"{self.agent_name}_json_parse_failed",
                error=str(e),
                content_preview=content[:200]
            )
            return []
        except Exception as e:
            logger.error(
                f"{self.agent_name}_parse_failed",
                error=str(e)
            )
            return []
    
    def _extract_reasoning(self, content: str) -> str:
        """Extract reasoning from response"""
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            return data.get("reasoning", "")
        except:
            return ""
    
    def _extract_score(self, content: str) -> Optional[int]:
        """Extract quality score from response"""
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            return data.get("overall_quality_score") or data.get("score")
        except:
            return None
    
    async def _self_reflect(
        self,
        code_file: CodeFile,
        issues: List[Issue],
        previous_analysis: str
    ) -> List[Issue]:
        """
        Have the agent reflect on its own analysis to reduce false positives
        """
        from config.prompts import SELF_REFLECTION_PROMPT
        
        try:
            reflection_prompt = SELF_REFLECTION_PROMPT.format(
                previous_analysis=previous_analysis,
                code_content=code_file.content
            )
            
            response = await self.llm_manager.generate(
                system_prompt="You are a self-reflective code reviewer.",
                user_prompt=reflection_prompt
            )
            
            reflection = json.loads(response["content"])
            
            # Remove false positives
            false_positive_ids = set(reflection.get("false_positives", []))
            issues = [
                issue for issue in issues 
                if issue.id not in false_positive_ids
            ]
            
            # Adjust confidence scores
            confidence_adjustments = reflection.get("confidence_adjustments", {})
            for issue in issues:
                if issue.id in confidence_adjustments:
                    issue.confidence = confidence_adjustments[issue.id]
            
            logger.info(
                f"{self.agent_name}_self_reflection_complete",
                false_positives=len(false_positive_ids),
                remaining_issues=len(issues)
            )
            
            return issues
            
        except Exception as e:
            logger.warning(
                f"{self.agent_name}_self_reflection_failed",
                error=str(e)
            )
            return issues  # Return original issues if reflection fails