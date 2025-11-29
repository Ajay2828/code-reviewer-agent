import hashlib
from typing import List, Dict, Any, Optional
from github import Github, GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository
import structlog

from config.settings import get_settings
from core.state import CodeFile, Issue

logger = structlog.get_logger()
settings = get_settings()


class GitHubIntegration:
    """
    GitHub API integration for pull request reviews
    
    Features:
    - Fetch PR files and diffs
    - Post review comments
    - Create review summaries
    - Update PR status
    """
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.GITHUB_TOKEN
        if not self.token:
            raise ValueError("GitHub token is required")
        
        self.github = Github(self.token)
        self.user = self.github.get_user()
        
        logger.info("github_integration_initialized", user=self.user.login)
    
    def get_repository(self, repo_full_name: str) -> Repository:
        """
        Get repository object
        
        Args:
            repo_full_name: Format "owner/repo"
        """
        try:
            return self.github.get_repo(repo_full_name)
        except GithubException as e:
            logger.error("get_repository_failed", repo=repo_full_name, error=str(e))
            raise
    
    def get_pull_request(self, repo_full_name: str, pr_number: int) -> PullRequest:
        """Get pull request object"""
        try:
            repo = self.get_repository(repo_full_name)
            return repo.get_pull(pr_number)
        except GithubException as e:
            logger.error(
                "get_pull_request_failed",
                repo=repo_full_name,
                pr=pr_number,
                error=str(e)
            )
            raise
    
    async def fetch_pr_files(
        self, 
        repo_full_name: str, 
        pr_number: int
    ) -> List[CodeFile]:
        """
        Fetch all files from a pull request
        
        Returns list of CodeFile objects with content
        """
        try:
            pr = self.get_pull_request(repo_full_name, pr_number)
            code_files = []
            
            for file in pr.get_files():
                # Skip deleted files
                if file.status == "removed":
                    continue
                
                # Skip binary files and large files
                if file.filename.endswith(('.png', '.jpg', '.gif', '.pdf')):
                    continue
                
                if file.changes > 1000:
                    logger.warning(
                        "skipping_large_file",
                        file=file.filename,
                        changes=file.changes
                    )
                    continue
                
                # Detect language from extension
                language = self._detect_language(file.filename)
                if language not in settings.SUPPORTED_LANGUAGES:
                    continue
                
                # Fetch file content
                try:
                    # For modified files, get the new version
                    content = pr.base.repo.get_contents(
                        file.filename,
                        ref=pr.head.sha
                    ).decoded_content.decode('utf-8')
                except:
                    # Fallback: use patch content
                    content = file.patch or ""
                
                # Create hash for caching
                file_hash = hashlib.md5(content.encode()).hexdigest()
                
                code_file = CodeFile(
                    path=file.filename,
                    content=content,
                    language=language,
                    size=len(content),
                    hash=file_hash
                )
                
                code_files.append(code_file)
                
                logger.info(
                    "file_fetched",
                    file=file.filename,
                    language=language,
                    size=len(content)
                )
            
            return code_files
            
        except Exception as e:
            logger.error(
                "fetch_pr_files_failed",
                repo=repo_full_name,
                pr=pr_number,
                error=str(e)
            )
            raise
    
    async def post_review_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        issue: Issue,
        commit_sha: str
    ) -> bool:
        """
        Post a review comment on a specific line
        
        Args:
            repo_full_name: Repository name
            pr_number: PR number
            issue: Issue to comment on
            commit_sha: Commit SHA to comment on
        """
        try:
            pr = self.get_pull_request(repo_full_name, pr_number)
            
            # Format comment body
            comment_body = self._format_issue_comment(issue)
            
            # Post comment
            pr.create_review_comment(
                body=comment_body,
                commit=pr.get_commits()[0],  # Use latest commit
                path=issue.id.split('_')[0] if '_' in issue.id else "unknown",
                line=issue.line_start
            )
            
            logger.info(
                "review_comment_posted",
                pr=pr_number,
                line=issue.line_start
            )
            return True
            
        except Exception as e:
            logger.error(
                "post_review_comment_failed",
                pr=pr_number,
                error=str(e)
            )
            return False
    
    async def post_review_summary(
        self,
        repo_full_name: str,
        pr_number: int,
        summary: str,
        issues: List[Issue],
        recommendation: str
    ) -> bool:
        """
        Post overall review summary as a PR comment
        """
        try:
            pr = self.get_pull_request(repo_full_name, pr_number)
            
            # Format summary
            comment = self._format_review_summary(summary, issues, recommendation)
            
            # Post as issue comment (shows at bottom of PR)
            pr.create_issue_comment(comment)
            
            logger.info("review_summary_posted", pr=pr_number)
            return True
            
        except Exception as e:
            logger.error(
                "post_review_summary_failed",
                pr=pr_number,
                error=str(e)
            )
            return False
    
    async def create_review(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",  # APPROVE, REQUEST_CHANGES, or COMMENT
        comments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Create a complete PR review
        
        Args:
            event: APPROVE, REQUEST_CHANGES, or COMMENT
            comments: List of inline comments
        """
        try:
            pr = self.get_pull_request(repo_full_name, pr_number)
            
            # Create review
            if comments:
                pr.create_review(
                    body=body,
                    event=event,
                    comments=comments
                )
            else:
                pr.create_review(body=body, event=event)
            
            logger.info(
                "review_created",
                pr=pr_number,
                event=event,
                comments=len(comments) if comments else 0
            )
            return True
            
        except Exception as e:
            logger.error("create_review_failed", pr=pr_number, error=str(e))
            return False
    
    def _detect_language(self, filename: str) -> str:
        """Detect programming language from filename"""
        extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.go': 'go',
            '.java': 'java',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.c': 'cpp',
            '.h': 'cpp',
            '.hpp': 'cpp'
        }
        
        ext = '.' + filename.split('.')[-1] if '.' in filename else ''
        return extension_map.get(ext, 'unknown')
    
    def _format_issue_comment(self, issue: Issue) -> str:
        """Format an issue as a GitHub comment"""
        severity_emoji = {
            'critical': '🔴',
            'major': '🟡',
            'minor': '🔵',
            'info': 'ℹ️'
        }
        
        emoji = severity_emoji.get(issue.severity, '⚠️')
        
        comment = f"{emoji} **{issue.title}**\n\n"
        comment += f"**Severity:** {issue.severity.upper()}\n"
        comment += f"**Category:** {issue.category}\n\n"
        comment += f"{issue.description}\n\n"
        
        if issue.suggestion:
            comment += f"**Suggestion:**\n{issue.suggestion}\n\n"
        
        if issue.suggested_code:
            comment += f"**Suggested Fix:**\n```\n{issue.suggested_code}\n```\n\n"
        
        comment += f"*Confidence: {int(issue.confidence * 100)}%*"
        
        return comment
    
    def _format_review_summary(
        self,
        summary: str,
        issues: List[Issue],
        recommendation: str
    ) -> str:
        """Format complete review summary"""
        
        # Count issues by severity
        severity_counts = {
            'critical': 0,
            'major': 0,
            'minor': 0,
            'info': 0
        }
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
        
        comment = "## 🤖 AI Code Review Summary\n\n"
        comment += f"{summary}\n\n"
        
        comment += "### 📊 Statistics\n"
        comment += f"- 🔴 Critical: {severity_counts['critical']}\n"
        comment += f"- 🟡 Major: {severity_counts['major']}\n"
        comment += f"- 🔵 Minor: {severity_counts['minor']}\n"
        comment += f"- ℹ️ Info: {severity_counts['info']}\n\n"
        
        comment += f"### 🎯 Recommendation: **{recommendation.upper()}**\n\n"
        
        comment += "*This review was generated by AI Code Review Agent*"
        
        return comment


def get_github_integration() -> GitHubIntegration:
    """Get GitHub integration instance"""
    return GitHubIntegration()