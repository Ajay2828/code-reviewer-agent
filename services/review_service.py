import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from langgraph.graph import StateGraph, END
from core.state import (
    ReviewState, 
    CodeFile, 
    create_initial_state,
    ReviewOutput,
    AgentResult
)
from agents.analyzer_agent import AnalyzerAgent
from agents.security_agent import SecurityAgent
from agents.optimizer_agent import OptimizerAgent
from agents.documenter_agent import DocumenterAgent
from services.cache_service import get_cache_service
from rag.knowledge_base import get_knowledge_base
from tools.github_integration import get_github_integration
from config.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()


class ReviewService:
    """
    Main review orchestration service using LangGraph
    
    Workflow:
    1. Fetch files (from GitHub or direct input)
    2. Check cache
    3. Run static analysis
    4. Query RAG for best practices
    5. Run specialized agents in parallel
    6. Consolidate results
    7. Generate summary
    8. Post results (if GitHub)
    """
    
    def __init__(self):
        self.analyzer = AnalyzerAgent()
        self.security = SecurityAgent()
        self.optimizer = OptimizerAgent()
        self.documenter = DocumenterAgent()
        
        self.reviews: Dict[str, Dict[str, Any]] = {}
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph workflow
        
        Graph structure:
        START -> static_analysis -> rag_query -> agents (parallel) -> consolidate -> END
        """
        workflow = StateGraph(ReviewState)
        
        # Add nodes
        workflow.add_node("static_analysis", self._static_analysis_node)
        workflow.add_node("rag_query", self._rag_query_node)
        workflow.add_node("run_agents", self._run_agents_node)
        workflow.add_node("consolidate", self._consolidate_node)
        
        # Define edges
        workflow.set_entry_point("static_analysis")
        workflow.add_edge("static_analysis", "rag_query")
        workflow.add_edge("rag_query", "run_agents")
        workflow.add_edge("run_agents", "consolidate")
        workflow.add_edge("consolidate", END)
        
        return workflow.compile()
    
    async def _static_analysis_node(self, state: ReviewState) -> ReviewState:
        """Run static analysis tools on all files"""
        logger.info("static_analysis_started", review_id=state["review_id"])
        
        from tools.static_analyzers import run_static_analysis
        
        results = []
        for code_file in state["files"]:
            result = await run_static_analysis(code_file)
            if result:
                results.append(result)
        
        state["static_analysis_results"] = results
        state["current_step"] = "static_analysis_complete"
        
        logger.info(
            "static_analysis_complete",
            review_id=state["review_id"],
            results=len(results)
        )
        
        return state
    
    async def _rag_query_node(self, state: ReviewState) -> ReviewState:
        """Query knowledge base for relevant best practices"""
        logger.info("rag_query_started", review_id=state["review_id"])
        
        kb = get_knowledge_base()
        best_practices = []
        
        for code_file in state["files"]:
            # Query for language-specific best practices
            results = await kb.retrieve_best_practices(
                query=f"best practices for {code_file.language}",
                language=code_file.language,
                top_k=3
            )
            best_practices.extend(results)
        
        state["relevant_best_practices"] = best_practices
        state["current_step"] = "rag_query_complete"
        
        logger.info(
            "rag_query_complete",
            review_id=state["review_id"],
            practices=len(best_practices)
        )
        
        return state
    
    async def _run_agents_node(self, state: ReviewState) -> ReviewState:
        """Run all agents in parallel"""
        logger.info("agents_started", review_id=state["review_id"])
        
        # Prepare context for agents
        context = {
            "static_analysis": state.get("static_analysis_results", []),
            "best_practices": state.get("relevant_best_practices", [])
        }
        
        # Check cache first
        cache_service = await get_cache_service()
        
        # Run agents in parallel for each file
        all_results = {
            "analyzer": [],
            "security": [],
            "optimizer": [],
            "documenter": []
        }
        
        for code_file in state["files"]:
            # Check cache for each agent
            cached_results = {}
            for agent_name in ["analyzer", "security", "optimizer", "documenter"]:
                cached = await cache_service.get_cached_result(
                    code_file.path,
                    code_file.hash,
                    agent_name
                )
                if cached:
                    cached_results[agent_name] = cached
            
            # Run agents that don't have cached results
            tasks = []
            agent_map = {
                "analyzer": self.analyzer,
                "security": self.security,
                "optimizer": self.optimizer,
                "documenter": self.documenter
            }
            
            for agent_name, agent in agent_map.items():
                if agent_name not in cached_results:
                    tasks.append((agent_name, agent.analyze(code_file, context)))
                else:
                    # Use cached result
                    all_results[agent_name].append(cached_results[agent_name])
            
            # Execute non-cached agents in parallel
            if tasks:
                results = await asyncio.gather(
                    *[task for _, task in tasks],
                    return_exceptions=True
                )
                
                # Store results and cache them
                for idx, (agent_name, _) in enumerate(tasks):
                    result = results[idx]
                    if not isinstance(result, Exception):
                        all_results[agent_name].append(result)
                        
                        # Cache result
                        await cache_service.set_cached_result(
                            code_file.path,
                            code_file.hash,
                            agent_name,
                            result.__dict__
                        )
        
        # Aggregate results
        state["analyzer_result"] = self._aggregate_agent_results(
            all_results["analyzer"]
        )
        state["security_result"] = self._aggregate_agent_results(
            all_results["security"]
        )
        state["optimizer_result"] = self._aggregate_agent_results(
            all_results["optimizer"]
        )
        state["documenter_result"] = self._aggregate_agent_results(
            all_results["documenter"]
        )
        
        state["current_step"] = "agents_complete"
        
        logger.info("agents_complete", review_id=state["review_id"])
        
        return state
    
    def _aggregate_agent_results(
        self, 
        results: List[AgentResult]
    ) -> AgentResult:
        """Aggregate results from multiple files"""
        if not results:
            return None
        
        # Combine all issues
        all_issues = []
        total_cost = 0.0
        total_time = 0.0
        
        for result in results:
            all_issues.extend(result.issues)
            total_cost += result.cost
            total_time += result.execution_time
        
        return AgentResult(
            agent_name=results[0].agent_name,
            issues=all_issues,
            reasoning="Aggregated from multiple files",
            execution_time=total_time,
            cost=total_cost,
            success=True
        )
    
    async def _consolidate_node(self, state: ReviewState) -> ReviewState:
        """Consolidate all agent results into final review"""
        logger.info("consolidation_started", review_id=state["review_id"])
        
        # Collect all issues
        all_issues = []
        
        for result_key in ["analyzer_result", "security_result", 
                          "optimizer_result", "documenter_result"]:
            result = state.get(result_key)
            if result and result.issues:
                all_issues.extend(result.issues)
        
        # Remove duplicates (issues found by multiple agents)
        unique_issues = self._deduplicate_issues(all_issues)
        
        # Sort by severity
        severity_order = {"critical": 0, "major": 1, "minor": 2, "info": 3}
        unique_issues.sort(
            key=lambda x: (severity_order.get(x.severity, 4), -x.confidence)
        )
        
        # Generate executive summary
        summary = self._generate_summary(unique_issues, state)
        
        # Calculate overall score
        overall_score = self._calculate_score(unique_issues)
        
        # Determine recommendation
        recommendation = self._determine_recommendation(unique_issues, overall_score)
        
        # Update state
        state["consolidated_issues"] = unique_issues
        state["executive_summary"] = summary
        state["overall_score"] = overall_score
        state["recommendation"] = recommendation
        state["completed_at"] = datetime.now()
        state["current_step"] = "complete"
        
        # Calculate total cost
        total_cost = sum([
            state.get("analyzer_result", AgentResult("", [], "", 0, 0)).cost,
            state.get("security_result", AgentResult("", [], "", 0, 0)).cost,
            state.get("optimizer_result", AgentResult("", [], "", 0, 0)).cost,
            state.get("documenter_result", AgentResult("", [], "", 0, 0)).cost,
        ])
        state["total_cost"] = total_cost
        
        logger.info(
            "consolidation_complete",
            review_id=state["review_id"],
            issues=len(unique_issues),
            score=overall_score,
            recommendation=recommendation
        )
        
        return state
    
    def _deduplicate_issues(self, issues):
        """Remove duplicate issues found by multiple agents"""
        # Group by file and line number
        issue_groups = {}
        for issue in issues:
            key = (issue.line_start, issue.category, issue.title[:50])
            if key not in issue_groups:
                issue_groups[key] = []
            issue_groups[key].append(issue)
        
        # Keep highest confidence version of each issue
        unique = []
        for group in issue_groups.values():
            if len(group) == 1:
                unique.append(group[0])
            else:
                # Merge sources and keep highest confidence
                best = max(group, key=lambda x: x.confidence)
                best.sources = list(set(sum([i.sources for i in group], [])))
                unique.append(best)
        
        return unique
    
    def _generate_summary(self, issues, state) -> str:
        """Generate executive summary"""
        critical = len([i for i in issues if i.severity == "critical"])
        major = len([i for i in issues if i.severity == "major"])
        
        if critical > 0:
            return f"⚠️ Code review found {critical} critical and {major} major issues that must be addressed before merging."
        elif major > 3:
            return f"⚠️ Code review found {major} major issues. Please address these before merging."
        elif major > 0:
            return f"✅ Code is generally good with {major} major issues to consider."
        else:
            return "✅ Code looks great! Only minor suggestions for improvement."
    
    def _calculate_score(self, issues) -> int:
        """Calculate overall quality score 0-100"""
        base_score = 100
        
        for issue in issues:
            if issue.severity == "critical":
                base_score -= 15
            elif issue.severity == "major":
                base_score -= 5
            elif issue.severity == "minor":
                base_score -= 2
        
        return max(0, min(100, base_score))
    
    def _determine_recommendation(self, issues, score) -> str:
        """Determine approve/request_changes/reject"""
        critical = len([i for i in issues if i.severity == "critical"])
        
        if critical > 0 or score < 50:
            return "reject"
        elif score < 70:
            return "request_changes"
        else:
            return "approve"
    
    async def execute_review(
        self,
        review_id: str,
        files: List[CodeFile],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a complete review"""
        try:
            # Create initial state
            state = create_initial_state(files, review_id, options)
            
            # Store in memory
            self.reviews[review_id] = {
                "status": "processing",
                "progress": 0,
                "result": None
            }
            
            # Run workflow
            final_state = await self.graph.ainvoke(state)
            
            # Convert to output format
            result = self._state_to_output(final_state)
            
            # Update storage
            self.reviews[review_id] = {
                "status": "completed",
                "progress": 100,
                "result": result
            }
            
            return result
            
        except Exception as e:
            logger.error("execute_review_failed", error=str(e))
            self.reviews[review_id] = {
                "status": "failed",
                "progress": 0,
                "error": str(e)
            }
            raise
    
    def _state_to_output(self, state: ReviewState) -> Dict[str, Any]:
        """Convert state to output format"""
        return {
            "review_id": state["review_id"],
            "files": [f.path for f in state["files"]],
            "executive_summary": state["executive_summary"],
            "overall_score": state["overall_score"],
            "recommendation": state["recommendation"],
            "statistics": {
                "total_issues": len(state["consolidated_issues"]),
                "by_severity": self._count_by_severity(state["consolidated_issues"]),
                "total_cost": state["total_cost"],
            },
            "issues": [self._issue_to_dict(i) for i in state["consolidated_issues"]],
            "metadata": {
                "created_at": state["created_at"].isoformat(),
                "completed_at": state["completed_at"].isoformat()
            }
        }
    
    def _count_by_severity(self, issues):
        counts = {"critical": 0, "major": 0, "minor": 0, "info": 0}
        for issue in issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts
    
    def _issue_to_dict(self, issue):
        return {
            "id": issue.id,
            "severity": issue.severity,
            "category": issue.category,
            "line_start": issue.line_start,
            "line_end": issue.line_end,
            "title": issue.title,
            "description": issue.description,
            "suggestion": issue.suggestion,
            "confidence": issue.confidence,
            "sources": issue.sources
        }
    
    async def get_review_status(self, review_id: str) -> Optional[Dict]:
        """Get review status"""
        return self.reviews.get(review_id)
    
    async def delete_review(self, review_id: str) -> bool:
        """Delete review"""
        if review_id in self.reviews:
            del self.reviews[review_id]
            return True
        return False
    
    async def execute_github_pr_review(
        self,
        review_id: str,
        repo_full_name: str,
        pr_number: int,
        post_comments: bool,
        options: Dict[str, Any]
    ):
        """Execute GitHub PR review"""
        try:
            # Fetch PR files
            github = get_github_integration()
            files = await github.fetch_pr_files(repo_full_name, pr_number)
            
            # Execute review
            result = await self.execute_review(review_id, files, options)
            
            # Post results to GitHub if requested
            if post_comments:
                await github.post_review_summary(
                    repo_full_name,
                    pr_number,
                    result["executive_summary"],
                    [Issue(**i) for i in result["issues"]],
                    result["recommendation"]
                )
            
            return result
            
        except Exception as e:
            logger.error("execute_github_pr_review_failed", error=str(e))
            raise