"""GitHub pull request creation."""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests

from codebot.core.github_app import GitHubAppAuth
from codebot.core.utils import detect_github_api_url, detect_github_info


class GitHubPR:
    """Create pull requests on GitHub."""
    
    def __init__(self, github_app_auth: Optional[GitHubAppAuth] = None, api_url: Optional[str] = None):
        """
        Initialize GitHub PR creator.
        
        Args:
            github_app_auth: GitHub App authentication instance (created if not provided)
            api_url: GitHub API URL (auto-detected if not provided)
        """
        if github_app_auth is None:
            github_app_auth = GitHubAppAuth(api_url=api_url)
        
        self.github_app_auth = github_app_auth
        
        self.default_api_url = api_url or detect_github_api_url()
        self._repo_api_cache = {}
    
    @property
    def headers(self) -> dict:
        return self.github_app_auth.get_auth_headers()
    
    def _get_api_url(self, repository_url: str) -> str:
        """
        Get GitHub API URL for the given repository.
        
        Args:
            repository_url: Git repository URL
            
        Returns:
            GitHub API base URL
        """
        try:
            github_info = detect_github_info(repository_url)
            return github_info["api_url"]
        except Exception:
            return self.default_api_url
    
    def _build_api_url(self, repository_url: str, endpoint: str) -> str:
        """
        Build full API URL for endpoint.
        
        Args:
            repository_url: Git repository URL (to determine API base)
            endpoint: API endpoint path
            
        Returns:
            Full API URL
        """
        api_base = self._get_api_url(repository_url)
        return f"{api_base}/{endpoint.lstrip('/')}"
    
    def _build_api_url_from_owner_repo(self, owner: str, repo: str, endpoint: str) -> str:
        """
        Build full API URL for endpoint using owner/repo.
        
        Args:
            owner: Repository owner
            repo: Repository name
            endpoint: API endpoint path
            
        Returns:
            Full API URL
        """
        repo_key = f"{owner}/{repo}"
        if repo_key in self._repo_api_cache:
            api_url = self._repo_api_cache[repo_key]
        else:
            api_url = self.default_api_url
        
        return f"{api_url}/{endpoint.lstrip('/')}"
    
    def extract_repo_info(self, repository_url: str) -> Tuple[str, str]:
        """
        Extract owner and repo name from repository URL.
        
        Args:
            repository_url: Git repository URL
            
        Returns:
            Tuple of (owner, repo)
        """
        parsed = urlparse(repository_url)
        
        if parsed.scheme in ["http", "https"]:
            path = parsed.path.strip("/")
        elif parsed.scheme == "" or "git@" in repository_url:
            path = parsed.path
            if path.startswith(":"):
                path = path[1:]
        else:
            raise ValueError(f"Unsupported repository URL format: {repository_url}")
        
        if path.endswith(".git"):
            path = path[:-4]
        
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
        
        repo_key = f"{owner}/{repo}"
        api_url = self._get_api_url(repository_url)
        self._repo_api_cache[repo_key] = api_url
        
        url = self._build_api_url(repository_url, f"repos/{owner}/{repo}/pulls")
        
        data = {
            "title": title,
            "body": body,
            "head": branch_name,
            "base": base_branch,
        }
        
        print(f"Creating pull request: {title}")
        print(f"  From branch: {branch_name}")
        print(f"  To branch: {base_branch}")
        print(f"  Repository: {owner}/{repo}")
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code != 201:
            error_data = response.json()
            error_msg = error_data.get("message", "Unknown error")
            
            if "errors" in error_data:
                error_details = "\n".join([f"  - {err.get('message', err)}" for err in error_data["errors"]])
                raise RuntimeError(
                    f"Failed to create pull request: {error_msg}\n"
                    f"Validation errors:\n{error_details}\n"
                    f"Request data: {data}"
                )
            else:
                raise RuntimeError(
                    f"Failed to create pull request: {error_msg}\n"
                    f"Status code: {response.status_code}\n"
                    f"Response: {error_data}\n"
                    f"Request data: {data}"
                )
        
        pr_data = response.json()
        pr_url = pr_data["html_url"]
        print(f"✅ Created pull request: {pr_url}")
        
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
        
        first_line = task.description.split("\n")[0]
        if len(first_line) > 100:
            first_line = first_line[:97] + "..."
        
        return first_line
    
    def _clean_commit_message(self, commit_message: str) -> str:
        """
        Clean commit message by removing unwanted lines.
        
        Args:
            commit_message: Original commit message
            
        Returns:
            Cleaned commit message
        """
        lines = commit_message.split("\n")
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped == "🤖 Generated with Claude Code" or "🤖 Generated with Claude Code" in stripped:
                continue
            if stripped.startswith("Co-Authored-By:"):
                continue
            cleaned_lines.append(line)
        
        cleaned = "\n".join(cleaned_lines).strip()
        while cleaned.endswith("\n\n"):
            cleaned = cleaned[:-1]
        
        return cleaned
    
    def generate_pr_body(
        self, 
        task: "TaskPrompt",  # type: ignore
        commit_message: Optional[str] = None,
        files_changed: Optional[str] = None,
    ) -> str:
        """
        Generate a PR body from the task.
        
        Args:
            task: Task prompt object
            commit_message: Optional commit message from Claude's changes
            files_changed: Optional list of files changed
            
        Returns:
            PR body text
        """
        body_parts = []
        
        if task.ticket_id:
            body_parts.append(f"**Ticket ID:** {task.ticket_id}")
            body_parts.append("")
        
        cleaned_task_description = self._clean_commit_message(task.description)
        body_parts.append("## 📋 Task Description")
        body_parts.append("")
        body_parts.append(cleaned_task_description)
        body_parts.append("")
        
        if commit_message:
            cleaned_message = self._clean_commit_message(commit_message)
            if cleaned_message.strip():
                body_parts.append("## 🔨 Changes Made")
                body_parts.append("")
                body_parts.append(cleaned_message)
                body_parts.append("")
        
        if files_changed:
            body_parts.append("## 📁 Files Changed")
            body_parts.append("")
            body_parts.append("```")
            body_parts.append(files_changed)
            body_parts.append("```")
            body_parts.append("")
        
        body_parts.append("---")
        body_parts.append("*This PR was automatically generated by [codebot](https://github.com/ajibigad/codebot) 🤖*")
        
        full_body = "\n".join(body_parts)
        return self._clean_commit_message(full_body)
    
    def get_pr_details(self, owner: str, repo: str, pr_number: int) -> dict:
        """
        Get pull request details.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            PR data from GitHub API
        """
        url = self._build_api_url_from_owner_repo(owner, repo, f"repos/{owner}/{repo}/pulls/{pr_number}")
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            raise RuntimeError(f"Failed to get PR details: {response.status_code}")
        
        return response.json()
    
    def get_pr_files_changed(self, owner: str, repo: str, pr_number: int) -> str:
        """
        Get list of files changed in a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            Formatted string of files changed
        """
        url = self._build_api_url_from_owner_repo(owner, repo, f"repos/{owner}/{repo}/pulls/{pr_number}/files")
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            raise RuntimeError(f"Failed to get PR files: {response.status_code}")
        
        files = response.json()
        result = []
        for file in files:
            status = file.get("status", "modified")[0].upper()  # M, A, D, etc.
            result.append(f"{status}    {file['filename']}")
        
        return "\n".join(result)
    
    def post_review_comment_reply(self, owner: str, repo: str, pr_number: int, comment_id: int, body: str) -> dict:
        """
        Reply to a pull request review comment in the same thread.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            comment_id: ID of the comment to reply to
            body: Reply text
            
        Returns:
            Comment data from GitHub API
        """
        url = self._build_api_url_from_owner_repo(owner, repo, f"repos/{owner}/{repo}/pulls/{pr_number}/comments")
        data = {
            "body": body,
            "in_reply_to": comment_id
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code != 201:
            raise RuntimeError(f"Failed to post reply: {response.status_code} - {response.text}")
        
        return response.json()
    
    def post_pr_comment(self, owner: str, repo: str, pr_number: int, body: str) -> dict:
        """
        Post a general comment on a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Comment text
            
        Returns:
            Comment data from GitHub API
        """
        url = self._build_api_url_from_owner_repo(owner, repo, f"repos/{owner}/{repo}/issues/{pr_number}/comments")
        data = {"body": body}
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code != 201:
            raise RuntimeError(f"Failed to post comment: {response.status_code} - {response.text}")
        
        return response.json()
    
    def update_pr_description(self, owner: str, repo: str, pr_number: int, title: str, body: str) -> dict:
        """
        Update a pull request's title and description.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            title: New PR title
            body: New PR body/description
            
        Returns:
            Updated PR data from GitHub API
        """
        cleaned_body = self._clean_commit_message(body)
        
        url = self._build_api_url_from_owner_repo(owner, repo, f"repos/{owner}/{repo}/pulls/{pr_number}")
        data = {
            "title": title,
            "body": cleaned_body
        }
        
        response = requests.patch(url, headers=self.headers, json=data)
        
        if response.status_code != 200:
            raise RuntimeError(f"Failed to update PR: {response.status_code} - {response.text}")
        
        return response.json()
    
    def get_comment_thread(self, owner: str, repo: str, pr_number: int, comment_id: int) -> list:
        """
        Get the comment thread for a specific review comment.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            comment_id: Comment ID to get thread for
            
        Returns:
            List of comments in the thread, ordered chronologically
        """
        url = self._build_api_url_from_owner_repo(owner, repo, f"repos/{owner}/{repo}/pulls/{pr_number}/comments")
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            return []
        
        all_comments = response.json()
        
        thread_comments = []
        current_id = comment_id
        
        comment_map = {c["id"]: c for c in all_comments}
        
        if current_id not in comment_map:
            return []
        
        current_comment = comment_map[current_id]
        
        thread_root_id = current_comment.get("in_reply_to_id")
        while thread_root_id and thread_root_id in comment_map:
            current_comment = comment_map[thread_root_id]
            thread_root_id = current_comment.get("in_reply_to_id")
        
        root_id = current_comment["id"]
        
        for comment in all_comments:
            if comment["id"] == root_id:
                thread_comments.append(comment)
            elif comment.get("in_reply_to_id") == root_id:
                thread_comments.append(comment)
            else:
                check_id = comment.get("in_reply_to_id")
                while check_id and check_id in comment_map:
                    if check_id == root_id:
                        thread_comments.append(comment)
                        break
                    check_id = comment_map[check_id].get("in_reply_to_id")
        
        thread_comments.sort(key=lambda c: c["created_at"])
        
        return thread_comments
    
    def get_pr_review_comments(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        since: Optional[str] = None,
    ) -> list:
        """
        Get review comments for a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            since: Optional ISO 8601 timestamp to fetch only comments created after this time
            
        Returns:
            List of review comments
        """
        url = self._build_api_url_from_owner_repo(owner, repo, f"repos/{owner}/{repo}/pulls/{pr_number}/comments")
        params = {}
        if since:
            params["since"] = since
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code != 200:
            raise RuntimeError(f"Failed to get PR review comments: {response.status_code}")
        
        return response.json()
    
    def get_pr_issue_comments(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        since: Optional[str] = None,
    ) -> list:
        """
        Get issue comments for a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            since: Optional ISO 8601 timestamp to fetch only comments created after this time
            
        Returns:
            List of issue comments
        """
        url = self._build_api_url_from_owner_repo(owner, repo, f"repos/{owner}/{repo}/issues/{pr_number}/comments")
        params = {}
        if since:
            params["since"] = since
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code != 200:
            raise RuntimeError(f"Failed to get PR issue comments: {response.status_code}")
        
        return response.json()
    
    def get_pr_reviews(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        since: Optional[str] = None,
    ) -> list:
        """
        Get reviews for a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            since: Optional ISO 8601 timestamp to fetch only reviews created after this time
            
        Returns:
            List of PR reviews
        """
        url = self._build_api_url_from_owner_repo(owner, repo, f"repos/{owner}/{repo}/pulls/{pr_number}/reviews")
        params = {}
        if since:
            params["since"] = since
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code != 200:
            raise RuntimeError(f"Failed to get PR reviews: {response.status_code}")
        
        return response.json()
    
    def get_pr_state(self, owner: str, repo: str, pr_number: int) -> dict:
        """
        Get current PR state (open/closed/merged).
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            Dictionary with PR state information (state, merged, etc.)
        """
        pr_details = self.get_pr_details(owner, repo, pr_number)
        return {
            "state": pr_details.get("state"),  # open, closed
            "merged": pr_details.get("merged", False),
            "merged_at": pr_details.get("merged_at"),
            "closed_at": pr_details.get("closed_at"),
        }