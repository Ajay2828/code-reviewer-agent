# api/routes/webhooks.py
"""
Webhook handlers for GitHub/GitLab
"""
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Header
from typing import Optional
import hmac
import hashlib
import structlog

from config.settings import get_settings
from services.review_service import ReviewService

logger = structlog.get_logger()
settings = get_settings()
router = APIRouter()
review_service = ReviewService()


def verify_github_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature"""
    if not settings.WEBHOOK_SECRET:
        return True  # Skip verification if no secret configured
    
    expected = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected}", signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(None),
    x_hub_signature_256: Optional[str] = Header(None)
):
    """
    GitHub webhook handler
    
    Automatically reviews PRs when:
    - PR is opened
    - PR is synchronized (new commits)
    """
    try:
        # Get payload
        payload = await request.body()
        
        # Verify signature
        if x_hub_signature_256:
            if not verify_github_signature(payload, x_hub_signature_256):
                raise HTTPException(status_code=403, detail="Invalid signature")
        
        # Parse payload
        import json
        data = json.loads(payload)
        
        # Only handle pull request events
        if x_github_event != "pull_request":
            return {"message": "Event ignored"}
        
        # Only handle opened and synchronized actions
        action = data.get("action")
        if action not in ["opened", "synchronize"]:
            return {"message": f"Action '{action}' ignored"}
        
        # Extract PR info
        pr = data.get("pull_request", {})
        repo = data.get("repository", {})
        
        repo_full_name = repo.get("full_name")
        pr_number = pr.get("number")
        
        if not repo_full_name or not pr_number:
            raise HTTPException(status_code=400, detail="Invalid payload")
        
        logger.info(
            "github_webhook_received",
            repo=repo_full_name,
            pr=pr_number,
            action=action
        )
        
        # Start review in background
        import uuid
        review_id = str(uuid.uuid4())
        
        background_tasks.add_task(
            review_service.execute_github_pr_review,
            review_id=review_id,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            post_comments=True,
            options={}
        )
        
        return {
            "message": "Review started",
            "review_id": review_id,
            "repo": repo_full_name,
            "pr": pr_number
        }
        
    except Exception as e:
        logger.error("github_webhook_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_gitlab_event: str = Header(None),
    x_gitlab_token: Optional[str] = Header(None)
):
    """
    GitLab webhook handler
    
    Similar to GitHub webhook but for GitLab
    """
    try:
        # Verify token
        if settings.WEBHOOK_SECRET:
            if x_gitlab_token != settings.WEBHOOK_SECRET:
                raise HTTPException(status_code=403, detail="Invalid token")
        
        # Get payload
        import json
        data = await request.json()
        
        # Only handle merge request events
        if x_gitlab_event != "Merge Request Hook":
            return {"message": "Event ignored"}
        
        # Extract MR info
        object_attributes = data.get("object_attributes", {})
        project = data.get("project", {})
        
        action = object_attributes.get("action")
        if action not in ["open", "update"]:
            return {"message": f"Action '{action}' ignored"}
        
        # Extract info
        project_path = project.get("path_with_namespace")
        mr_iid = object_attributes.get("iid")
        
        logger.info(
            "gitlab_webhook_received",
            project=project_path,
            mr=mr_iid,
            action=action
        )
        
        # GitLab MR review would be implemented similarly to GitHub
        # Using GitLab API instead
        
        return {
            "message": "GitLab webhook received",
            "project": project_path,
            "mr": mr_iid
        }
        
    except Exception as e:
        logger.error("gitlab_webhook_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
