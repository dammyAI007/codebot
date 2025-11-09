"""GitHub webhook handlers for PR review comments."""

import hashlib
import hmac
import os
from pathlib import Path
from queue import Queue

from flask import current_app, request, jsonify


# Global FIFO queue for review comments
review_queue: Queue = Queue()


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify GitHub webhook signature.
    
    Args:
        payload: Request payload bytes
        signature: X-Hub-Signature-256 header value
        secret: Webhook secret
        
    Returns:
        True if signature is valid
    """
    if not signature or not secret:
        return False
    
    # GitHub sends signature as "sha256=<hash>"
    if not signature.startswith("sha256="):
        return False
    
    expected_signature = signature[7:]  # Remove "sha256=" prefix
    
    # Compute HMAC
    mac = hmac.new(secret.encode(), payload, hashlib.sha256)
    computed_signature = mac.hexdigest()
    
    # Constant-time comparison
    return hmac.compare_digest(computed_signature, expected_signature)


def handle_webhook():
    """Handle incoming GitHub webhook events."""
    # Get webhook secret from environment
    webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    
    if not webhook_secret:
        current_app.logger.error("GITHUB_WEBHOOK_SECRET not set")
        return jsonify({"error": "Webhook secret not configured"}), 500
    
    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.data, signature, webhook_secret):
        current_app.logger.warning("Invalid webhook signature")
        return jsonify({"error": "Invalid signature"}), 401
    
    # Get event type
    event_type = request.headers.get("X-GitHub-Event", "")
    
    # Parse payload
    payload = request.json
    
    if not payload:
        return jsonify({"error": "Invalid payload"}), 400
    
    # Handle pull request comment events
    if event_type == "pull_request_review_comment":
        return handle_review_comment(payload)
    elif event_type == "pull_request_review":
        return handle_review(payload)
    elif event_type == "issue_comment":
        return handle_issue_comment(payload)
    elif event_type == "pull_request":
        return handle_pull_request(payload)
    else:
        current_app.logger.info(f"Ignoring event type: {event_type}")
        return jsonify({"message": "Event type not handled"}), 200


def handle_review_comment(payload: dict) -> tuple:
    """
    Handle pull_request_review_comment event.
    
    Args:
        payload: GitHub webhook payload
        
    Returns:
        Response tuple (data, status_code)
    """
    action = payload.get("action")
    
    if action != "created":
        return jsonify({"message": f"Ignoring action: {action}"}), 200
    
    comment = payload.get("comment", {})
    comment_body = comment.get("body", "")
    
    # Check if comment is from codebot by checking user login
    comment_user = comment.get("user", {})
    comment_user_login = comment_user.get("login", "")
    bot_login = current_app.config.get("CODEBOT_BOT_LOGIN", "codebot-007[bot]")
    
    if comment_user_login == bot_login:
        current_app.logger.info(f"Ignoring codebot's own comment (detected by user login: {comment_user_login})")
        return jsonify({"message": "Ignoring codebot's own comment"}), 200
    
    pull_request = payload.get("pull_request", {})
    repository = payload.get("repository", {})
    
    # Extract relevant information
    comment_data = {
        "type": "review_comment",
        "comment_id": comment.get("id"),
        "comment_body": comment.get("body", ""),
        "pr_number": pull_request.get("number"),
        "pr_title": pull_request.get("title"),
        "pr_body": pull_request.get("body", ""),
        "branch_name": pull_request.get("head", {}).get("ref"),
        "repo_url": repository.get("clone_url"),
        "repo_owner": repository.get("owner", {}).get("login"),
        "repo_name": repository.get("name"),
        "comment_path": comment.get("path"),
        "comment_line": comment.get("line"),
        "comment_diff_hunk": comment.get("diff_hunk", ""),
        "comment_position": comment.get("position"),
        "in_reply_to_id": comment.get("in_reply_to_id"),
    }
    
    # Add to queue
    review_queue.put(comment_data)
    
    current_app.logger.info(f"Queued review comment for PR #{comment_data['pr_number']}")
    
    return jsonify({"message": "Comment queued for processing"}), 200


def handle_review(payload: dict) -> tuple:
    """
    Handle pull_request_review event (review submitted with comments).
    
    Args:
        payload: GitHub webhook payload
        
    Returns:
        Response tuple (data, status_code)
    """
    action = payload.get("action")
    
    if action != "submitted":
        return jsonify({"message": f"Ignoring action: {action}"}), 200
    
    review = payload.get("review", {})
    review_body = review.get("body") or ""
    
    # Check if review is from codebot by checking user login
    review_user = review.get("user", {})
    review_user_login = review_user.get("login", "")
    bot_login = current_app.config.get("CODEBOT_BOT_LOGIN", "codebot-007[bot]")
    
    if review_user_login == bot_login:
        current_app.logger.info(f"Ignoring codebot's own review (detected by user login: {review_user_login})")
        return jsonify({"message": "Ignoring codebot's own review"}), 200
    
    pull_request = payload.get("pull_request", {})
    repository = payload.get("repository", {})
    
    # Skip if review has no body (only inline comments)
    if not review_body.strip():
        return jsonify({"message": "Review has no body, skipping"}), 200
    
    comment_data = {
        "type": "review",
        "comment_id": review.get("id"),
        "comment_body": review_body,
        "pr_number": pull_request.get("number"),
        "pr_title": pull_request.get("title"),
        "pr_body": pull_request.get("body", ""),
        "branch_name": pull_request.get("head", {}).get("ref"),
        "repo_url": repository.get("clone_url"),
        "repo_owner": repository.get("owner", {}).get("login"),
        "repo_name": repository.get("name"),
        "review_state": review.get("state"),  # APPROVED, CHANGES_REQUESTED, COMMENTED
    }
    
    # Add to queue
    review_queue.put(comment_data)
    
    current_app.logger.info(f"Queued review for PR #{comment_data['pr_number']}")
    
    return jsonify({"message": "Review queued for processing"}), 200


def handle_issue_comment(payload: dict) -> tuple:
    """
    Handle issue_comment event (comments on PRs).
    
    GitHub treats PR comments as issue comments, so we need to check if this
    is actually a PR comment and not just a regular issue comment.
    
    Args:
        payload: GitHub webhook payload
        
    Returns:
        Response tuple (data, status_code)
    """
    action = payload.get("action")
    
    if action != "created":
        return jsonify({"message": f"Ignoring action: {action}"}), 200
    
    issue = payload.get("issue", {})
    if not issue.get("pull_request"):
        current_app.logger.info("Ignoring non-PR issue comment")
        return jsonify({"message": "Not a PR comment"}), 200
    
    comment = payload.get("comment", {})
    comment_body = comment.get("body", "")
    
    # Check if comment is from codebot by checking user login
    comment_user = comment.get("user", {})
    comment_user_login = comment_user.get("login", "")
    bot_login = current_app.config.get("CODEBOT_BOT_LOGIN", "codebot-007[bot]")
    
    if comment_user_login == bot_login:
        current_app.logger.info(f"Ignoring codebot's own comment (detected by user login: {comment_user_login})")
        return jsonify({"message": "Ignoring codebot's own comment"}), 200
    
    repository = payload.get("repository", {})
    
    # Extract PR number from issue
    pr_number = issue.get("number")
    
    # Extract relevant information
    comment_data = {
        "type": "issue_comment",
        "comment_id": comment.get("id"),
        "comment_body": comment.get("body", ""),
        "pr_number": pr_number,
        "pr_title": issue.get("title"),
        "pr_body": issue.get("body", ""),
        "branch_name": None,  # Will be fetched from PR details
        "repo_url": repository.get("clone_url"),
        "repo_owner": repository.get("owner", {}).get("login"),
        "repo_name": repository.get("name"),
    }
    
    # Add to queue
    review_queue.put(comment_data)
    
    current_app.logger.info(f"Queued issue comment for PR #{comment_data['pr_number']}")
    
    return jsonify({"message": "Comment queued for processing"}), 200


def handle_pull_request(payload: dict) -> tuple:
    """
    Handle pull_request event (PR opened, closed, merged, etc.).
    
    Args:
        payload: GitHub webhook payload
        
    Returns:
        Response tuple (data, status_code)
    """
    action = payload.get("action")
    
    # Only handle closed PRs (merged or just closed)
    if action != "closed":
        return jsonify({"message": f"Ignoring action: {action}"}), 200
    
    pull_request = payload.get("pull_request", {})
    branch_name = pull_request.get("head", {}).get("ref", "")
    
    # Only clean up workspaces for codebot branches
    if not branch_name.startswith("u/codebot/"):
        current_app.logger.info(f"Ignoring non-codebot branch: {branch_name}")
        return jsonify({"message": "Not a codebot branch"}), 200
    
    # Extract UUID from branch name
    from codebot.core.utils import extract_uuid_from_branch, find_workspace_by_uuid, cleanup_workspace
    
    uuid = extract_uuid_from_branch(branch_name)
    if not uuid:
        current_app.logger.warning(f"Could not extract UUID from branch: {branch_name}")
        return jsonify({"message": "Could not extract UUID from branch"}), 200
    
    # Get workspace base directory from app config
    workspace_base_dir_str = current_app.config.get("CODEBOT_WORKSPACE_BASE_DIR")
    if not workspace_base_dir_str:
        current_app.logger.warning("CODEBOT_WORKSPACE_BASE_DIR not configured")
        return jsonify({"message": "Workspace base directory not configured"}), 200
    
    workspace_base_dir = Path(workspace_base_dir_str)
    
    # Find workspace by UUID
    workspace_path = find_workspace_by_uuid(workspace_base_dir, uuid)
    if not workspace_path:
        current_app.logger.info(f"No workspace found for UUID: {uuid}")
        return jsonify({"message": "Workspace not found"}), 200
    
    # Check if PR was merged or just closed
    merged = pull_request.get("merged", False)
    pr_number = pull_request.get("number")
    
    if merged:
        current_app.logger.info(f"PR #{pr_number} merged, cleaning up workspace: {workspace_path}")
    else:
        current_app.logger.info(f"PR #{pr_number} closed (not merged), cleaning up workspace: {workspace_path}")
    
    # Clean up workspace
    if cleanup_workspace(workspace_path):
        current_app.logger.info(f"Successfully cleaned up workspace: {workspace_path}")
        return jsonify({"message": "Workspace cleaned up successfully"}), 200
    else:
        current_app.logger.warning(f"Failed to clean up workspace: {workspace_path}")
        return jsonify({"message": "Failed to clean up workspace"}), 500



