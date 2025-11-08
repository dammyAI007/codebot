"""Git operations for committing and pushing changes."""

import subprocess
from pathlib import Path
from typing import Optional

from codebot.core.github_app import GitHubAppAuth
from codebot.core.utils import get_git_env


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
        """Get git environment variables for non-interactive operation."""
        return get_git_env()
    
    def _create_authenticated_url(self, repository_url: str) -> str:
        """
        Create authenticated URL for GitHub repository.
        
        Args:
            repository_url: Original repository URL
            
        Returns:
            Authenticated URL with embedded token
        """
        from urllib.parse import urlparse
        from codebot.core.utils import is_github_url
        
        if not self.github_app_auth or not is_github_url(repository_url):
            return repository_url
        
        parsed = urlparse(repository_url)
        if not parsed.netloc:
            return repository_url
        
        # Extract repo path
        path = parsed.path
        if not path.endswith(".git"):
            path += ".git"
        
        # Get installation token from GitHub App auth
        token = self.github_app_auth.get_installation_token()
        
        # Build authenticated URL using oauth2 format
        auth_url = f"https://oauth2:{token}@{parsed.netloc}{path}"
        return auth_url
    
    def _get_remote_url(self) -> Optional[str]:
        """Get the current remote origin URL."""
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
        """Set the remote origin URL."""
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
        
        # Stage all changes
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to stage changes: {result.stderr}")
        
        # Commit
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
        
        # For GitHub repositories with GitHub App auth, temporarily use authenticated URL
        original_url = None
        if self.github_app_auth:
            original_url = self._get_remote_url()
            if original_url:
                auth_url = self._create_authenticated_url(original_url)
                if auth_url != original_url:
                    print("Setting up authenticated remote for push...")
                    self._set_remote_url(auth_url)
        
        try:
            # Push branch to remote
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
            # Restore original URL for security
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

