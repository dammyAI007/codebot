"""Git operations for committing and pushing changes."""

import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from codebot.core.github_app import GitHubAppAuth
from codebot.core.utils import get_git_env, is_github_url


class GitOps:
    """Git operations for codebot."""
    
    def __init__(self, work_dir: Path, github_app_auth: Optional[GitHubAppAuth] = None):
        """
        Initialize git operations.
        
        Args:
            work_dir: Working directory with git repository
            github_app_auth: Optional GitHub App authentication instance
        """
        self.work_dir = work_dir
        self.github_app_auth = github_app_auth
    
    def _get_git_env(self) -> dict:
        bot_user_id = None
        bot_name = None
        api_url = None
        if self.github_app_auth:
            bot_user_id = self.github_app_auth.bot_user_id
            bot_name = self.github_app_auth.get_bot_login()
            api_url = self.github_app_auth.api_url
            if not bot_user_id:
                bot_user_id = self.github_app_auth.app_id
        return get_git_env(bot_user_id=bot_user_id, bot_name=bot_name, api_url=api_url)
    
    def _create_authenticated_url(self, repository_url: str) -> str:
        """
        Create authenticated URL for GitHub repository.
        
        Args:
            repository_url: Original repository URL
            
        Returns:
            Authenticated URL with embedded token
        """
        if not self.github_app_auth or not is_github_url(repository_url):
            return repository_url
        
        parsed = urlparse(repository_url)
        if not parsed.netloc:
            return repository_url
        
        path = parsed.path
        if not path.endswith(".git"):
            path += ".git"
        
        token = self.github_app_auth.get_installation_token()
        auth_url = f"https://oauth2:{token}@{parsed.netloc}{path}"
        return auth_url
    
    def _get_remote_url(self) -> Optional[str]:
        env = self._get_git_env()
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    
    def _set_remote_url(self, url: str) -> None:
        env = self._get_git_env()
        result = subprocess.run(
            ["git", "remote", "set-url", "origin", url],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to set remote URL: {result.stderr}")
    
    def commit_changes(self, message: str) -> None:
        """
        Commit all changes with the given message.
        
        Args:
            message: Commit message
        """
        env = self._get_git_env()
        
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to stage changes: {result.stderr}")
        
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to commit: {result.stderr}")
        
        print(f"Committed changes: {message}")
    
    def push_branch(self, branch_name: str) -> None:
        """
        Push the branch to remote origin.
        
        Args:
            branch_name: Name of the branch to push
        """
        env = self._get_git_env()
        
        original_url = None
        if self.github_app_auth:
            original_url = self._get_remote_url()
            if original_url:
                auth_url = self._create_authenticated_url(original_url)
                if auth_url != original_url:
                    print("Setting up authenticated remote for push...")
                    self._set_remote_url(auth_url)
        
        try:
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                env=env,
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to push branch: {result.stderr}")
            
            print(f"Pushed branch {branch_name} to remote")
            
        finally:
            if original_url and self.github_app_auth:
                print("Restoring clean remote URL...")
                self._set_remote_url(original_url)
    
    def has_uncommitted_changes(self) -> bool:
        """
        Check if there are uncommitted changes.
        
        Returns:
            True if there are uncommitted changes, False otherwise
        """
        env = self._get_git_env()
        
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        return result.stdout.strip() != ""
    
    def get_latest_commit_hash(self) -> Optional[str]:
        """
        Get the hash of the latest commit.
        
        Returns:
            Commit hash or None if no commits exist
        """
        env = self._get_git_env()
        
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        
        return None
    
    def get_current_branch(self) -> Optional[str]:
        """
        Get the name of the current branch.
        
        Returns:
            Branch name or None if no branch is checked out
        """
        env = self._get_git_env()
        
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        
        return None
    
    def get_commit_message(self, commit_hash: str) -> str:
        """
        Get the commit message for a specific commit.
        
        Args:
            commit_hash: Commit hash
            
        Returns:
            Commit message
        """
        env = self._get_git_env()
        
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B", commit_hash],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to get commit message: {result.stderr}")
        
        return result.stdout.strip()
    
    def remove_co_author_trailers(self) -> None:
        """
        Remove Co-Authored-By trailers and unwanted text from the latest commit.
        
        Claude Code CLI adds "Co-Authored-By: Claude" trailers and "🤖 Generated with Claude Code"
        text to commits. This method rewrites the commit to remove those.
        """
        env = self._get_git_env()
        
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%B"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            print(f"Warning: Failed to get commit message: {result.stderr}")
            return
        
        commit_message = result.stdout
        
        lines = commit_message.split("\n")
        cleaned_lines = []
        has_unwanted = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Co-Authored-By:"):
                has_unwanted = True
                continue
            if stripped == "🤖 Generated with Claude Code" or "🤖 Generated with Claude Code" in stripped:
                has_unwanted = True
                continue
            cleaned_lines.append(line)
        
        if not has_unwanted:
            return
        
        cleaned_message = "\n".join(cleaned_lines).strip()
        while cleaned_message.endswith("\n\n"):
            cleaned_message = cleaned_message[:-1]
        
        result = subprocess.run(
            ["git", "commit", "--amend", "-m", cleaned_message],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            print(f"Warning: Failed to clean commit message: {result.stderr}")
        else:
            print("Cleaned commit message (removed Co-Authored-By trailers and unwanted text)")
    
    def _is_authenticated_url(self, url: str) -> bool:
        """Check if URL contains authentication token."""
        return "oauth2:" in url or "@" in url and "token" in url
    
    def fetch_from_remote(self) -> bool:
        """
        Fetch latest changes from remote with proper authentication.
        
        Returns:
            True if fetch was successful, False otherwise
        """
        print("Fetching latest changes from remote...")
        
        original_url = None
        
        if self.github_app_auth:
            original_url = self._get_remote_url()
            if original_url and not self._is_authenticated_url(original_url):
                auth_url = self._create_authenticated_url(original_url)
                print("Setting up authenticated remote URL for fetch...")
                self._set_remote_url(auth_url)
        
        try:
            env = self._get_git_env()
            result = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                env=env,
            )
            
            if result.returncode != 0:
                print(f"Warning: Failed to fetch from remote: {result.stderr.strip()}")
                return False
            
            print("Successfully fetched from remote")
            return True
            
        finally:
            if self.github_app_auth and original_url:
                print("Restoring clean remote URL...")
                self._set_remote_url(original_url)
    
    def pull_latest_changes(self, branch_name: str) -> bool:
        """
        Pull latest changes from the specified branch with proper authentication.
        
        Args:
            branch_name: Name of the branch to pull from
            
        Returns:
            True if pull was successful, False otherwise
        """
        print(f"Pulling latest changes from branch: {branch_name}")
        
        original_url = None
        
        if self.github_app_auth:
            original_url = self._get_remote_url()
            if original_url and not self._is_authenticated_url(original_url):
                auth_url = self._create_authenticated_url(original_url)
                print("Setting up authenticated remote URL for pull...")
                self._set_remote_url(auth_url)
        
        try:
            env = self._get_git_env()
            result = subprocess.run(
                ["git", "pull", "origin", branch_name],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                env=env,
            )
            
            if result.returncode != 0:
                print(f"Warning: Failed to pull latest changes: {result.stderr.strip()}")
                return False
            
            print("Successfully pulled latest changes")
            return True
            
        finally:
            if self.github_app_auth and original_url:
                print("Restoring clean remote URL...")
                self._set_remote_url(original_url)

