"""Process PR review comments from the queue."""

import os
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

from codebot.environment import EnvironmentManager
from codebot.git_ops import GitOps
from codebot.github_pr import GitHubPR
from codebot.models import TaskPrompt
from codebot.review_runner import ReviewRunner
from codebot.utils import extract_uuid_from_branch, find_workspace_by_uuid


class ReviewProcessor:
    """Process review comments from the queue."""
    
    def __init__(
        self,
        review_queue: Queue,
        workspace_base_dir: Path,
        github_token: str,
    ):
        """
        Initialize the review processor.
        
        Args:
            review_queue: Queue containing review comments to process
            workspace_base_dir: Base directory for workspaces
            github_token: GitHub personal access token
        """
        self.review_queue = review_queue
        self.workspace_base_dir = workspace_base_dir
        self.github_token = github_token
        self.github_pr = GitHubPR(github_token)
        self.running = False
    
    def start(self):
        """Start processing review comments from the queue."""
        self.running = True
        print("Review processor started")
        
        while self.running:
            try:
                # Get next comment from queue (wait up to 5 seconds)
                comment_data = self.review_queue.get(timeout=5)
                
                print(f"\n{'=' * 80}")
                print(f"Processing review comment for PR #{comment_data['pr_number']}")
                print(f"{'=' * 80}\n")
                
                # Process the comment
                self.process_comment(comment_data)
                
                # Mark task as done
                self.review_queue.task_done()
                
            except Empty:
                # No items in queue, continue waiting
                continue
            except KeyboardInterrupt:
                print("\nStopping review processor...")
                self.running = False
                break
            except Exception as e:
                print(f"ERROR: Failed to process review comment: {e}")
                # Continue processing other comments
                continue
    
    def stop(self):
        """Stop the review processor."""
        self.running = False
    
    def process_comment(self, comment_data: dict):
        """
        Process a single review comment.
        
        Args:
            comment_data: Dictionary with comment information
        """
        # Extract data
        pr_number = comment_data["pr_number"]
        branch_name = comment_data["branch_name"]
        repo_url = comment_data["repo_url"]
        repo_owner = comment_data["repo_owner"]
        repo_name = comment_data["repo_name"]
        comment_body = comment_data["comment_body"]
        comment_id = comment_data["comment_id"]
        
        print(f"Branch: {branch_name}")
        print(f"Comment: {comment_body[:100]}...")
        
        # Derive workspace from branch name
        workspace_path = self._get_or_create_workspace(
            branch_name,
            repo_url,
            pr_number,
        )
        
        if not workspace_path:
            print("ERROR: Failed to setup workspace")
            return
        
        print(f"Workspace: {workspace_path}")
        
        # Get PR context
        pr_context = self._get_pr_context(repo_owner, repo_name, pr_number)
        
        # Classify comment as query or change request
        is_change_request = self._classify_comment(comment_body)
        
        if is_change_request:
            print("Classification: CHANGE REQUEST")
        else:
            print("Classification: QUERY")
        
        # Run Claude Code to handle the comment
        print("\nRunning Claude Code...")
        review_runner = ReviewRunner(workspace_path)
        
        try:
            result = review_runner.handle_review_comment(
                comment_body=comment_body,
                pr_context=pr_context,
                is_change_request=is_change_request,
            )
            
            if result.returncode != 0:
                print(f"ERROR: Claude Code failed with exit code {result.returncode}")
                self._post_error_reply(
                    repo_owner,
                    repo_name,
                    comment_id,
                    comment_data["type"],
                    pr_number,
                )
                return
            
            print("Claude Code completed successfully")
            
        except Exception as e:
            print(f"ERROR: Failed to run Claude Code: {e}")
            self._post_error_reply(
                repo_owner,
                repo_name,
                comment_id,
                comment_data["type"],
                pr_number,
            )
            return
        
        # Check if changes were made
        git_ops = GitOps(workspace_path)
        
        if is_change_request:
            # Check for new commits
            try:
                # Push changes if any
                print("\nPushing changes to remote...")
                git_ops.push_branch(branch_name)
                print("Changes pushed successfully")
                
                # Get commit message for reply
                commit_hash = git_ops.get_latest_commit_hash()
                commit_msg = git_ops.get_commit_message(commit_hash)
                
                # Post reply indicating changes were made
                reply_body = (
                    f"✅ Changes have been made to address this review comment.\n\n"
                    f"**Commit:** {commit_hash[:7]}\n"
                    f"**Message:** {commit_msg}\n\n"
                    f"*Reply generated by codebot 🤖*"
                )
                
            except Exception as e:
                print(f"Note: No new commits to push: {e}")
                reply_body = (
                    f"ℹ️ I've reviewed this comment. No code changes were necessary.\n\n"
                    f"*Reply generated by codebot 🤖*"
                )
        else:
            # For queries, extract response from Claude's output
            # For now, just acknowledge
            reply_body = (
                f"ℹ️ Thank you for the question. Claude Code has reviewed this.\n\n"
                f"Please check the conversation history for the detailed response.\n\n"
                f"*Reply generated by codebot 🤖*"
            )
        
        # Post reply to the comment
        print("\nPosting reply to GitHub...")
        try:
            if comment_data["type"] == "review_comment":
                self.github_pr.post_review_comment_reply(
                    repo_owner,
                    repo_name,
                    comment_id,
                    reply_body,
                )
            else:
                # For review-level comments, post as general PR comment
                self.github_pr.post_pr_comment(
                    repo_owner,
                    repo_name,
                    pr_number,
                    reply_body,
                )
            print("Reply posted successfully")
        except Exception as e:
            print(f"ERROR: Failed to post reply: {e}")
    
    def _get_or_create_workspace(
        self,
        branch_name: str,
        repo_url: str,
        pr_number: int,
    ) -> Optional[Path]:
        """
        Get existing workspace or create a new one.
        
        Args:
            branch_name: Branch name
            repo_url: Repository URL
            pr_number: PR number
            
        Returns:
            Path to workspace or None if failed
        """
        # Try to find existing workspace by UUID
        uuid = extract_uuid_from_branch(branch_name)
        
        if uuid:
            workspace_path = find_workspace_by_uuid(self.workspace_base_dir, uuid)
            
            if workspace_path and workspace_path.exists():
                print(f"Found existing workspace: {workspace_path}")
                
                # Reuse and update workspace
                task = TaskPrompt(
                    description=f"Review comment on PR #{pr_number}",
                    repository_url=repo_url,
                )
                
                env_manager = EnvironmentManager(task, self.github_token)
                
                try:
                    env_manager.reuse_workspace(
                        workspace_path,
                        branch_name,
                        repo_url,
                    )
                    return workspace_path
                except Exception as e:
                    print(f"Warning: Failed to reuse workspace: {e}")
                    print("Will create a new workspace instead")
        
        # If no existing workspace, create a new one
        print("Creating new workspace...")
        task = TaskPrompt(
            description=f"Review comment on PR #{pr_number}",
            repository_url=repo_url,
        )
        
        env_manager = EnvironmentManager(task, self.github_token)
        
        try:
            # Clone and checkout the branch
            workspace_path = env_manager._create_work_directory(
                self.workspace_base_dir,
                ticket_id=None,
                uuid_part=uuid,
            )
            env_manager.work_dir = workspace_path
            env_manager._clone_repository()
            
            # Checkout the PR branch
            env_manager.branch_name = branch_name
            env_manager._checkout_branch(branch_name)
            
            return workspace_path
            
        except Exception as e:
            print(f"ERROR: Failed to create workspace: {e}")
            return None
    
    def _get_pr_context(self, owner: str, repo: str, pr_number: int) -> dict:
        """
        Get PR context for Claude.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            
        Returns:
            Dictionary with PR context
        """
        try:
            pr_details = self.github_pr.get_pr_details(owner, repo, pr_number)
            files_changed = self.github_pr.get_pr_files_changed(owner, repo, pr_number)
            
            return {
                "pr_title": pr_details.get("title", ""),
                "pr_body": pr_details.get("body", ""),
                "files_changed": files_changed,
            }
        except Exception as e:
            print(f"Warning: Failed to get PR context: {e}")
            return {
                "pr_title": "",
                "pr_body": "",
                "files_changed": "",
            }
    
    def _classify_comment(self, comment_body: str) -> bool:
        """
        Classify a comment as query or change request.
        
        Uses simple heuristics to determine if the comment is asking for changes.
        
        Args:
            comment_body: Comment text
            
        Returns:
            True if change request, False if query
        """
        # Convert to lowercase for matching
        body_lower = comment_body.lower()
        
        # Keywords that indicate change requests
        change_keywords = [
            "please change",
            "please fix",
            "please update",
            "please add",
            "please remove",
            "can you change",
            "can you fix",
            "can you update",
            "can you add",
            "can you remove",
            "could you change",
            "could you fix",
            "could you update",
            "could you add",
            "could you remove",
            "should change",
            "should fix",
            "should update",
            "should add",
            "should remove",
            "needs to be changed",
            "needs to be fixed",
            "needs to be updated",
            "must change",
            "must fix",
            "must update",
        ]
        
        # Check for change keywords
        for keyword in change_keywords:
            if keyword in body_lower:
                return True
        
        # Default to query if no change keywords found
        return False
    
    def _post_error_reply(
        self,
        owner: str,
        repo: str,
        comment_id: int,
        comment_type: str,
        pr_number: int,
    ):
        """
        Post an error reply when Claude Code fails.
        
        Args:
            owner: Repository owner
            repo: Repository name
            comment_id: Comment ID
            comment_type: Type of comment (review_comment or review)
            pr_number: PR number
        """
        error_body = (
            "❌ I encountered an error while processing this review comment.\n\n"
            "Please try again or contact the maintainers.\n\n"
            "*Reply generated by codebot 🤖*"
        )
        
        try:
            if comment_type == "review_comment":
                self.github_pr.post_review_comment_reply(
                    owner,
                    repo,
                    comment_id,
                    error_body,
                )
            else:
                self.github_pr.post_pr_comment(
                    owner,
                    repo,
                    pr_number,
                    error_body,
                )
        except Exception as e:
            print(f"ERROR: Failed to post error reply: {e}")

