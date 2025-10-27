"""GitHub pull request creation."""

import os
import re
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests


class GitHubPR:
    """Create pull requests on GitHub."""
    
    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize GitHub PR creator.
        
        Args:
            github_token: GitHub personal access token (defaults to GITHUB_TOKEN env var or .env file)
        """
        self.token = github_token or os.getenv("GITHUB_TOKEN")
        
        if not self.token:
            raise RuntimeError(
                "GitHub token not found. Please set GITHUB_TOKEN environment variable or add it to a .env file."
            )
        
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
    
    def extract_repo_info(self, repository_url: str) -> Tuple[str, str]:
        """
        Extract owner and repo name from repository URL.
        
        Args:
            repository_url: Git repository URL
            
        Returns:
            Tuple of (owner, repo)
        """
        # Parse the URL
        parsed = urlparse(repository_url)
        
        if parsed.scheme in ["http", "https"]:
            # HTTPS URL: https://github.com/owner/repo.git
            path = parsed.path.strip("/")
        elif parsed.scheme == "" or "git@" in repository_url:
            # SSH URL or path: git@github.com:owner/repo.git or owner/repo
            path = parsed.path
            if path.startswith(":"):
                path = path[1:]
        else:
            raise ValueError(f"Unsupported repository URL format: {repository_url}")
        
        # Remove .git suffix if present
        if path.endswith(".git"):
            path = path[:-4]
        
        # Split into owner and repo
        parts = path.split("/")
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        
        raise ValueError(f"Could not parse repository owner/name from: {repository_url}")
    
    def create_pull_request(
        self,
        repository_url: str,
        branch_name: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> dict:
        """
        Create a pull request on GitHub.
        
        Args:
            repository_url: Repository URL
            branch_name: Branch name to create PR from
            base_branch: Base branch (usually main/master)
            title: PR title
            body: PR body/description
            
        Returns:
            Pull request data from GitHub API
        """
        owner, repo = self.extract_repo_info(repository_url)
        
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        
        data = {
            "title": title,
            "body": body,
            "head": branch_name,
            "base": base_branch,
        }
        
        print(f"Creating pull request: {title}")
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code != 201:
            error_msg = response.json().get("message", "Unknown error")
            raise RuntimeError(f"Failed to create pull request: {error_msg}")
        
        pr_data = response.json()
        pr_url = pr_data["html_url"]
        print(f"Created pull request: {pr_url}")
        
        return pr_data
    
    def generate_pr_title(self, task: "TaskPrompt") -> str:  # type: ignore
        """
        Generate a PR title from the task.
        
        Args:
            task: Task prompt object
            
        Returns:
            PR title
        """
        if task.ticket_summary:
            return task.ticket_summary
        
        # Use first line of description as title
        first_line = task.description.split("\n")[0]
        # Truncate if too long
        if len(first_line) > 100:
            first_line = first_line[:97] + "..."
        
        return first_line
    
    def generate_pr_body(self, task: "TaskPrompt") -> str:  # type: ignore
        """
        Generate a PR body from the task.
        
        Args:
            task: Task prompt object
            
        Returns:
            PR body text
        """
        body_parts = []
        
        if task.ticket_id:
            body_parts.append(f"**Ticket ID:** {task.ticket_id}")
            body_parts.append("")
        
        body_parts.append("## Task Description")
        body_parts.append("")
        body_parts.append(task.description)
        
        # TODO: Explore GitHub MCP integration for AI agent
        
        return "\n".join(body_parts)
