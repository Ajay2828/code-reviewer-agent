from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
import asyncio
import json
import structlog

from services.review_service import ReviewService
from core.state import CodeFile

logger = structlog.get_logger()
router = APIRouter()


# Request Models
class CodeReviewRequest(BaseModel):
    """Request model for code review"""
    files: List[Dict[str, str]] = Field(
        ...,
        description="List of files with 'path', 'content', and 'language'"
    )
    options: Optional[Dict[str, Any]] = Field(
        default={},
        description="Review options (e.g., enable_security, enable_performance)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "files": [
                    {
                        "path": "app.py",
                        "content": "def add(a, b):\n    return a + b",
                        "language": "python"
                    }
                ],
                "options": {
                    "enable_security": True,
                    "enable_performance": True,
                    "enable_documentation": True
                }
            }
        }


class GitHubPRReviewRequest(BaseModel):
    """Request model for GitHub PR review"""
    repo_full_name: str = Field(..., description="Repository in format 'owner/repo'")
    pr_number: int = Field(..., description="Pull request number")
    post_comments: bool = Field(
        default=True,
        description="Whether to post comments on GitHub"
    )
    options: Optional[Dict[str, Any]] = Field(default={})
    
    class Config:
        schema_extra = {
            "example": {
                "repo_full_name": "owner/repository",
                "pr_number": 123,
                "post_comments": True
            }
        }


class ReviewStatusResponse(BaseModel):
    """Response for review status check"""
    review_id: str
    status: str  # pending, processing, completed, failed
    progress: int  # 0-100
    result: Optional[Dict[str, Any]] = None


# Initialize review service
review_service = ReviewService()


@router.post("/review", response_model=Dict[str, Any])
async def create_review(
    request: CodeReviewRequest,
    background_tasks: BackgroundTasks
):
    """
    Create a code review
    
    This endpoint accepts code files and initiates a review.
    Returns immediately with a review_id that can be used to check status.
    """
    try:
        # Validate request
        if not request.files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        if len(request.files) > 50:
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 files per review"
            )
        
        # Convert to CodeFile objects
        code_files = []
        for file_data in request.files:
            import hashlib
            content = file_data.get("content", "")
            code_file = CodeFile(
                path=file_data.get("path", "unknown"),
                content=content,
                language=file_data.get("language", "python"),
                size=len(content),
                hash=hashlib.md5(content.encode()).hexdigest()
            )
            code_files.append(code_file)
        
        # Create review
        review_id = str(uuid.uuid4())
        
        # Start review in background
        background_tasks.add_task(
            review_service.execute_review,
            review_id=review_id,
            files=code_files,
            options=request.options
        )
        
        logger.info(
            "review_created",
            review_id=review_id,
            files=len(code_files)
        )
        
        return {
            "review_id": review_id,
            "status": "pending",
            "message": "Review started. Use /review/{review_id}/status to check progress."
        }
        
    except Exception as e:
        logger.error("create_review_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review/sync", response_model=Dict[str, Any])
async def create_review_sync(request: CodeReviewRequest):
    """
    Create a code review (synchronous)
    
    This endpoint waits for the review to complete before returning.
    Use for smaller reviews or when immediate results are needed.
    """
    try:
        # Convert to CodeFile objects
        code_files = []
        for file_data in request.files:
            import hashlib
            content = file_data.get("content", "")
            code_file = CodeFile(
                path=file_data.get("path", "unknown"),
                content=content,
                language=file_data.get("language", "python"),
                size=len(content),
                hash=hashlib.md5(content.encode()).hexdigest()
            )
            code_files.append(code_file)
        
        # Execute review
        review_id = str(uuid.uuid4())
        result = await review_service.execute_review(
            review_id=review_id,
            files=code_files,
            options=request.options
        )
        
        return result
        
    except Exception as e:
        logger.error("create_review_sync_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review/github-pr", response_model=Dict[str, Any])
async def review_github_pr(
    request: GitHubPRReviewRequest,
    background_tasks: BackgroundTasks
):
    """
    Review a GitHub pull request
    
    This endpoint fetches files from a GitHub PR and reviews them.
    Optionally posts results back to GitHub as PR comments.
    """
    try:
        review_id = str(uuid.uuid4())
        
        # Start GitHub PR review in background
        background_tasks.add_task(
            review_service.execute_github_pr_review,
            review_id=review_id,
            repo_full_name=request.repo_full_name,
            pr_number=request.pr_number,
            post_comments=request.post_comments,
            options=request.options
        )
        
        logger.info(
            "github_pr_review_created",
            review_id=review_id,
            repo=request.repo_full_name,
            pr=request.pr_number
        )
        
        return {
            "review_id": review_id,
            "status": "pending",
            "repo": request.repo_full_name,
            "pr_number": request.pr_number,
            "message": "GitHub PR review started"
        }
        
    except Exception as e:
        logger.error("review_github_pr_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review/{review_id}/status", response_model=ReviewStatusResponse)
async def get_review_status(review_id: str):
    """
    Get the status of a review
    
    Returns the current status and result if completed.
    """
    try:
        status = await review_service.get_review_status(review_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Review not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_review_status_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review/{review_id}/stream")
async def stream_review(review_id: str):
    """
    Stream review progress in real-time
    
    Returns Server-Sent Events (SSE) with progress updates.
    """
    async def event_generator():
        try:
            while True:
                status = await review_service.get_review_status(review_id)
                
                if not status:
                    yield f"data: {json.dumps({'error': 'Review not found'})}\n\n"
                    break
                
                yield f"data: {json.dumps(status)}\n\n"
                
                if status["status"] in ["completed", "failed"]:
                    break
                
                await asyncio.sleep(1)  # Poll every second
                
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.delete("/review/{review_id}")
async def delete_review(review_id: str):
    """Delete a review and its results"""
    try:
        deleted = await review_service.delete_review(review_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Review not found")
        
        return {"message": "Review deleted", "review_id": review_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_review_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))