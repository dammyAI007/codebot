"""GitHub PR comment poller for environments without webhook access."""

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from queue import Queue
from typing import Optional
from urllib.parse import urlparse

from codebot.core.github_app import GitHubAppAuth
from codebot.core.github_pr import GitHubPR
from codebot.core.task_store import global_task_store
from codebot.core.utils import cleanup_pr_workspace


class GitHubPoller:
    """Polls GitHub PRs for new comments on tasks in pending_review status."""
    
    def __init__(
        self,
        review_queue: Queue,
        workspace_base_dir: Path,
        github_app_auth: GitHubAppAuth,
        poll_interval: int = 300,
        reset_poll_times: bool = False,
    ):
        """
        Initialize the GitHub poller.
        
        Args:
            review_queue: Queue to add new comments to
            workspace_base_dir: Base directory for workspaces
            github_app_auth: GitHub App authentication instance
            poll_interval: Poll interval in seconds (default: 300)
            reset_poll_times: If True, reset poll times for all pending_review PRs to start from PR creation
        """
        self.review_queue = review_queue
        self.workspace_base_dir = workspace_base_dir
        self.github_app_auth = github_app_auth
        self.github_pr = GitHubPR(github_app_auth)
        self.poll_interval = poll_interval
        self.reset_poll_times = reset_poll_times
        self.running = False
        self.bot_login = github_app_auth.get_bot_login()
    
    def start(self):
        """Start polling for new comments."""
        self.running = True
        print(f"GitHub poller started (interval: {self.poll_interval}s)")
        
        while self.running:
            try:
                self._poll_once()
            except Exception as e:
                print(f"ERROR: Polling failed: {e}")
            
            # Sleep for poll interval
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def stop(self):
        """Stop polling."""
        self.running = False
        print("GitHub poller stopped")
    
    def _poll_once(self):
        """Perform one polling cycle."""
        # Get all tasks with pending_review status
        tasks = global_task_store.list_tasks(status_filter="pending_review", limit=1000)
        
        if not tasks:
            return
        
        print(f"Polling {len(tasks)} PR(s) for new comments...")
        
        for task in tasks:
            if not self.running:
                break
            
            try:
                self._poll_task_pr(task)
            except Exception as e:
                print(f"ERROR: Failed to poll PR for task {task.id}: {e}")
                continue
    
    def _poll_task_pr(self, task):
        """Poll a single task's PR for new comments."""
        if not task.result:
            return
        
        pr_url = task.result.get("pr_url")
        if not pr_url:
            return
        
        # Extract repo owner, name, and PR number from PR URL
        repo_owner, repo_name, pr_number = self._parse_pr_url(pr_url)
        if not all([repo_owner, repo_name, pr_number]):
            return
        
        # Check PR state and update task status if needed
        try:
            pr_state = self.github_pr.get_pr_state(repo_owner, repo_name, pr_number)
            
            if pr_state["state"] == "closed":
                merged = pr_state.get("merged", False)
                
                # Clean up workspace using central cleanup function (also updates task status)
                branch_name = task.result.get("branch_name")
                if branch_name:
                    success, message = cleanup_pr_workspace(
                        branch_name=branch_name,
                        workspace_base_dir=self.workspace_base_dir,
                        pr_number=pr_number,
                        pr_url=pr_url,
                        merged=merged,
                    )
                    if success:
                        print(message)
                        if merged:
                            print(f"PR #{pr_number} merged, task {task.id} updated to completed")
                        else:
                            print(f"PR #{pr_number} closed (not merged), task {task.id} updated to rejected")
                    else:
                        print(f"Warning: {message}")
                else:
                    # Branch name missing - still update task status even if we can't clean up workspace
                    if merged:
                        print(f"PR #{pr_number} merged, updating task {task.id} to completed (workspace cleanup skipped - no branch name)")
                        global_task_store.update_task(
                            task.id,
                            status="completed",
                            completed_at=datetime.utcnow()
                        )
                    else:
                        print(f"PR #{pr_number} closed (not merged), updating task {task.id} to rejected (workspace cleanup skipped - no branch name)")
                        global_task_store.update_task(
                            task.id,
                            status="rejected",
                            completed_at=datetime.utcnow()
                        )
                
                return
            elif pr_state["state"] == "open":
                # PR is open - ensure task is in pending_review status
                # This handles the case where a PR was reopened after being closed
                if task.status in ["rejected", "completed"]:
                    print(f"PR #{pr_number} is open, updating task {task.id} back to pending_review")
                    global_task_store.update_task(
                        task.id,
                        status="pending_review",
                        completed_at=None
                    )
        except Exception as e:
            print(f"Warning: Failed to check PR state for task {task.id}: {e}")
        
        # Get last poll time (or use PR creation time for first poll)
        storage = global_task_store.storage
        last_poll_time = storage.get_last_poll_time(repo_owner, repo_name, pr_number)
        
        # If reset_poll_times is enabled, clear existing poll time to start fresh from PR creation
        if self.reset_poll_times and last_poll_time:
            print(f"Resetting poll time for PR #{pr_number} (will start from PR creation)")
            # Clear the stored poll time so we use PR creation time below
            last_poll_time = None
        
        if not last_poll_time:
            # First poll - use PR creation time or 24 hours ago as fallback
            # Subtract 1 minute to ensure we catch comments created right at PR creation
            try:
                pr_details = self.github_pr.get_pr_details(repo_owner, repo_name, pr_number)
                created_at = pr_details.get("created_at")
                if created_at:
                    pr_created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    # Use 1 minute before PR creation to catch any comments created at the same time
                    last_poll_time = pr_created - timedelta(minutes=1)
                    print(f"First poll for PR #{pr_number}, using PR creation time: {pr_created} (since: {last_poll_time})")
                else:
                    last_poll_time = datetime.utcnow() - timedelta(days=1)
                    print(f"First poll for PR #{pr_number}, PR creation time not found, using 24h ago: {last_poll_time}")
            except Exception as e:
                last_poll_time = datetime.utcnow() - timedelta(days=1)
                print(f"First poll for PR #{pr_number}, error getting PR details: {e}, using 24h ago: {last_poll_time}")
        else:
            # For subsequent polls, subtract 30 seconds to account for timing differences
            # and ensure we don't miss comments created right at the poll boundary
            original_last_poll = last_poll_time
            last_poll_time = last_poll_time - timedelta(seconds=30)
            print(f"Subsequent poll for PR #{pr_number}, last poll was: {original_last_poll}, using: {last_poll_time}")
        
        # Convert to ISO 8601 format for GitHub API (must be UTC with Z suffix)
        # GitHub API expects format like: 2025-01-11T08:39:51Z
        if last_poll_time.tzinfo is None:
            # Naive datetime - assume UTC
            last_poll_time_utc = last_poll_time.replace(tzinfo=timezone.utc)
        else:
            last_poll_time_utc = last_poll_time.astimezone(timezone.utc)
        
        # Format as ISO 8601 with Z suffix for GitHub API
        since_timestamp = last_poll_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Poll for new comments
        new_comments_found = False
        
        print(f"Polling PR #{pr_number} since {since_timestamp} (last_poll_time: {last_poll_time})")
        
        # Poll review comments
        try:
            review_comments = self.github_pr.get_pr_review_comments(
                repo_owner, repo_name, pr_number, since=since_timestamp
            )
            print(f"Found {len(review_comments)} review comment(s) for PR #{pr_number} (since {since_timestamp})")
            for comment in review_comments:
                if self._should_process_comment(comment, "review_comment"):
                    self._add_comment_to_queue(comment, task, repo_owner, repo_name, pr_number, "review_comment")
                    new_comments_found = True
                else:
                    comment_id = comment.get("id")
                    comment_user = comment.get("user", {}).get("login", "")
                    print(f"Skipping review comment {comment_id} from {comment_user}")
        except Exception as e:
            print(f"Warning: Failed to fetch review comments for PR #{pr_number}: {e}")
        
        # Poll issue comments
        try:
            issue_comments = self.github_pr.get_pr_issue_comments(
                repo_owner, repo_name, pr_number, since=since_timestamp
            )
            print(f"Found {len(issue_comments)} issue comment(s) for PR #{pr_number} (since {since_timestamp})")
            for comment in issue_comments:
                if self._should_process_comment(comment, "issue_comment"):
                    self._add_comment_to_queue(comment, task, repo_owner, repo_name, pr_number, "issue_comment")
                    new_comments_found = True
                else:
                    comment_id = comment.get("id")
                    comment_user = comment.get("user", {}).get("login", "")
                    print(f"Skipping issue comment {comment_id} from {comment_user}")
        except Exception as e:
            print(f"Warning: Failed to fetch issue comments for PR #{pr_number}: {e}")
        
        # Poll reviews
        try:
            reviews = self.github_pr.get_pr_reviews(
                repo_owner, repo_name, pr_number, since=since_timestamp
            )
            print(f"Found {len(reviews)} review(s) for PR #{pr_number}")
            for review in reviews:
                if self._should_process_review(review):
                    self._add_review_to_queue(review, task, repo_owner, repo_name, pr_number)
                    new_comments_found = True
                else:
                    review_id = review.get("id")
                    review_user = review.get("user", {}).get("login", "")
                    print(f"Skipping review {review_id} from {review_user} (state: {review.get('state')})")
        except Exception as e:
            print(f"Warning: Failed to fetch reviews for PR #{pr_number}: {e}")
        
        # Update last poll time to the time we started this poll (before subtracting the buffer)
        # This ensures we don't miss comments created during the poll
        # Only update if we actually processed comments or if this is the first poll
        # This prevents updating to a future time that would miss existing comments
        if new_comments_found or not storage.get_last_poll_time(repo_owner, repo_name, pr_number):
            poll_start_time = datetime.utcnow()
            storage.update_last_poll_time(
                repo_owner, repo_name, pr_number, poll_start_time
            )
            print(f"Updated last poll time for PR #{pr_number} to {poll_start_time}")
        else:
            print(f"Keeping existing poll time for PR #{pr_number} (no new comments found)")
    
    def _should_process_comment(self, comment: dict, comment_type: str) -> bool:
        """Check if a comment should be processed."""
        # Skip if comment is from the bot
        comment_user = comment.get("user", {})
        comment_user_login = comment_user.get("login", "")
        if comment_user_login == self.bot_login:
            return False
        
        # Check if already processed
        comment_id = comment.get("id")
        if not comment_id:
            return False
        
        # Extract repo info from comment if available, otherwise we'll use task's repo
        # For now, we'll check in _add_comment_to_queue where we have full context
        
        return True
    
    def _should_process_review(self, review: dict) -> bool:
        """Check if a review should be processed."""
        review_id = review.get("id")
        review_user = review.get("user", {})
        review_user_login = review_user.get("login", "")
        
        # Skip if review is from the bot
        if review_user_login == self.bot_login:
            print(f"Skipping review {review_id} from bot ({review_user_login})")
            return False
        
        # Process reviews with valid states (COMMENTED, APPROVED, CHANGES_REQUESTED, DISMISSED, PENDING)
        # According to GitHub API: APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED, PENDING
        review_state = review.get("state")
        valid_states = ["COMMENTED", "APPROVED", "CHANGES_REQUESTED"]
        if review_state not in valid_states:
            print(f"Skipping review {review_id} - invalid state: {review_state}")
            return False
        
        review_body = review.get("body") or ""
        
        # Process reviews even without a body if they have meaningful states
        # APPROVED and CHANGES_REQUESTED are important even without a body
        # COMMENTED with no body can be skipped since inline comments are processed separately
        if not review_body.strip():
            if review_state in ["APPROVED", "CHANGES_REQUESTED"]:
                # Use a default body based on state
                review_body = (
                    "PR approved" if review_state == "APPROVED"
                    else "Changes requested"
                )
                print(f"Review {review_id} with state {review_state} has no body, using default message")
            else:
                # COMMENTED state with no body - skip since inline comments are processed separately
                print(f"Skipping review {review_id} - no body and state is COMMENTED (inline comments processed separately)")
                return False
        
        print(f"Processing review {review_id} from {review_user_login} (state: {review_state}, body: {review_body[:50]}...)")
        return True
    
    def _add_comment_to_queue(
        self,
        comment: dict,
        task,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        comment_type: str,
    ):
        """Add a comment to the review queue."""
        comment_id = comment.get("id")
        
        # Check if already processed
        storage = global_task_store.storage
        if storage.is_comment_processed(comment_id, repo_owner, repo_name, pr_number, comment_type):
            print(f"Comment {comment_id} already processed, skipping")
            return
        
        # Get PR details for branch name
        try:
            pr_details = self.github_pr.get_pr_details(repo_owner, repo_name, pr_number)
            branch_name = pr_details.get("head", {}).get("ref")
            pr_title = pr_details.get("title", "")
            pr_body = pr_details.get("body", "")
        except Exception as e:
            print(f"Warning: Failed to get PR details: {e}")
            branch_name = None
            pr_title = ""
            pr_body = ""
        
        # Build comment data similar to webhook handler
        comment_data = {
            "type": comment_type,
            "comment_id": comment_id,
            "comment_body": comment.get("body", ""),
            "pr_number": pr_number,
            "pr_title": pr_title,
            "pr_body": pr_body,
            "branch_name": branch_name,
            "repo_url": task.prompt.repository_url,
            "repo_owner": repo_owner,
            "repo_name": repo_name,
        }
        
        # Add comment-specific fields
        if comment_type == "review_comment":
            comment_data["comment_path"] = comment.get("path")
            comment_data["comment_line"] = comment.get("line")
            comment_data["comment_diff_hunk"] = comment.get("diff_hunk", "")
            comment_data["in_reply_to_id"] = comment.get("in_reply_to_id")
        
        # Mark as processed and add to queue
        storage.mark_comment_processed(comment_id, repo_owner, repo_name, pr_number, comment_type)
        self.review_queue.put(comment_data)
        
        print(f"Queued {comment_type} for PR #{pr_number} (comment ID: {comment_id})")
    
    def _add_review_to_queue(
        self,
        review: dict,
        task,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
    ):
        """Add a review to the review queue."""
        review_id = review.get("id")
        comment_type = "review"
        
        # Check if already processed
        storage = global_task_store.storage
        if storage.is_comment_processed(review_id, repo_owner, repo_name, pr_number, comment_type):
            return
        
        # Get PR details
        try:
            pr_details = self.github_pr.get_pr_details(repo_owner, repo_name, pr_number)
            branch_name = pr_details.get("head", {}).get("ref")
            pr_title = pr_details.get("title", "")
            pr_body = pr_details.get("body", "")
        except Exception as e:
            print(f"Warning: Failed to get PR details: {e}")
            branch_name = None
            pr_title = ""
            pr_body = ""
        
        # Get review body, using default if empty but state is meaningful
        review_body = review.get("body", "")
        review_state = review.get("state")
        if not review_body.strip() and review_state in ["APPROVED", "CHANGES_REQUESTED"]:
            review_body = (
                "PR approved" if review_state == "APPROVED"
                else "Changes requested"
            )
        
        # Build review data
        comment_data = {
            "type": comment_type,
            "comment_id": review_id,
            "comment_body": review_body,
            "pr_number": pr_number,
            "pr_title": pr_title,
            "pr_body": pr_body,
            "branch_name": branch_name,
            "repo_url": task.prompt.repository_url,
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "review_state": review_state,
        }
        
        # Mark as processed and add to queue
        storage.mark_comment_processed(review_id, repo_owner, repo_name, pr_number, comment_type)
        self.review_queue.put(comment_data)
        
        print(f"Queued review for PR #{pr_number} (review ID: {review_id})")
    
    def _parse_pr_url(self, pr_url: str) -> tuple:
        """
        Parse PR URL to extract owner, repo, and PR number.
        
        Args:
            pr_url: PR URL (e.g., https://github.com/owner/repo/pull/123)
            
        Returns:
            Tuple of (owner, repo, pr_number) or (None, None, None) if parsing fails
        """
        try:
            parsed = urlparse(pr_url)
            path_parts = parsed.path.strip("/").split("/")
            
            if len(path_parts) >= 4 and path_parts[2] == "pull":
                owner = path_parts[0]
                repo = path_parts[1]
                pr_number = int(path_parts[3])
                return (owner, repo, pr_number)
        except Exception:
            pass
        
        return (None, None, None)

