"""Environment manager for isolated development environments."""

import subprocess
from pathlib import Path
from typing import Optional, Tuple

from codebot.core.github_app import GitHubAppAuth
from codebot.core.models import TaskPrompt
from codebot.core.utils import (
    generate_branch_name, 
    generate_directory_name, 
    generate_short_uuid, 
    get_codebot_git_author_info,
    get_git_env,
    is_github_url
)


class EnvironmentManager:
    """Manages isolated development environments for codebot tasks."""
    
    def __init__(self, base_dir: Path, task: TaskPrompt, github_app_auth: Optional[GitHubAppAuth] = None):
        """
        Initialize the environment manager.
        
        Args:
            base_dir: Base directory for creating temporary workspaces
            task: Task prompt containing repository and task details
            github_app_auth: GitHub App authentication instance (optional)
        """
        self.base_dir = base_dir
        self.task = task
        self.github_app_auth = github_app_auth
        self.work_dir: Optional[Path] = None
        self.branch_name: Optional[str] = None
        self.default_branch: Optional[str] = None
    
    def setup_environment(self) -> Path:
        """
        Setup the isolated environment by creating directory, cloning repo, and checking out branch.
        
        Returns:
            Path to the working directory
        """
        # Generate a single UUID for both directory and branch name
        uuid_part = generate_short_uuid()
        
        # Create work directory
        dir_name = generate_directory_name(self.task.ticket_id, uuid_part)
        self.work_dir = self.base_dir / dir_name
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Created work directory: {self.work_dir}")
        
        # Clone repository
        self._clone_repository()
        
        # Configure git author for codebot
        self._configure_git_author()
        
        # Detect default branch
        self.default_branch = self._detect_default_branch()
        print(f"Detected default branch: {self.default_branch}")
        
        # Checkout base branch if specified, otherwise use default
        base_branch = self.task.base_branch or self.default_branch
        self._checkout_branch(base_branch)
        
        # Generate and checkout new branch using the same UUID
        self.branch_name = generate_branch_name(
            ticket_id=self.task.ticket_id,
            short_name=self.task.ticket_summary,
            uuid_part=uuid_part,
        )
        print(f"Creating branch: {self.branch_name}")
        self._create_branch(self.branch_name)
        
        return self.work_dir
    
    def reuse_workspace(self, work_dir: Path, branch_name: str, repo_url: str) -> Path:
        """
        Reuse an existing workspace and update it to latest remote state.
        
        Args:
            work_dir: Path to existing workspace
            branch_name: Branch name to checkout
            repo_url: Repository URL for authentication
            
        Returns:
            Path to the working directory
        """
        self.work_dir = work_dir
        self.branch_name = branch_name
        self.task.repository_url = repo_url
        
        print(f"Reusing workspace: {self.work_dir}")
        print(f"Updating branch: {branch_name}")
        
        # Update workspace to latest remote state
        self._update_workspace()
        
        # Configure git author for codebot
        self._configure_git_author()
        
        return self.work_dir
    
    def _update_workspace(self) -> None:
        """Update workspace to latest remote state."""
        if not self.work_dir:
            return
        
        env = get_git_env()
        
        # Fetch latest from remote
        print("Fetching latest changes from remote...")
        result = subprocess.run(
            ["git", "fetch", "origin"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            print(f"Warning: Failed to fetch from remote: {result.stderr}")
        
        # Checkout the branch
        print(f"Checking out branch: {self.branch_name}")
        result = subprocess.run(
            ["git", "checkout", self.branch_name],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to checkout branch: {result.stderr}")
        
        # Pull latest changes
        print("Pulling latest changes...")
        result = subprocess.run(
            ["git", "pull", "origin", self.branch_name],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            print(f"Warning: Failed to pull latest changes: {result.stderr}")
        
        print("Workspace updated successfully")
    
    def _create_authenticated_url(self, repo_url: str) -> str:
        """
        Create authenticated URL for GitHub repository.
        
        Args:
            repo_url: Original repository URL
            
        Returns:
            Authenticated URL with embedded token
        """
        from urllib.parse import urlparse
        
        if not self.github_app_auth:
            return repo_url
        
        parsed = urlparse(repo_url)
        if not parsed.netloc:
            return repo_url
        
        # Extract repo path
        path = parsed.path
        if path.endswith(".git"):
            path = path[:-4]
        if not path.endswith(".git"):
            path += ".git"
        
        # Get installation token from GitHub App auth
        token = self.github_app_auth.get_installation_token()
        
        # Build authenticated URL using oauth2 format
        auth_url = f"https://oauth2:{token}@{parsed.netloc}{path}"
        return auth_url
    
    def _clone_repository(self) -> None:
        """Clone the repository into the work directory."""
        # Prepare repository URL with authentication if GitHub App auth is available
        repo_url = self.task.repository_url
        
        if self.github_app_auth and is_github_url(repo_url):
            repo_url = self._create_authenticated_url(repo_url)
            print(f"Cloning repository with authentication")
        else:
            print(f"Cloning repository: {repo_url}")
        
        # Configure git environment for non-interactive operation
        env = get_git_env()
        
        result = subprocess.run(
            ["git", "clone", repo_url, str(self.work_dir)],
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            # Provide more helpful error messages for common authentication issues
            error_msg = result.stderr.lower()
            if "authentication failed" in error_msg or "401" in error_msg:
                raise RuntimeError(
                    f"Authentication failed. Please check your GitHub App configuration and permissions.\n"
                    f"Error: {result.stderr}"
                )
            elif "not found" in error_msg or "404" in error_msg:
                raise RuntimeError(
                    f"Repository not found or access denied. Please check the repository URL and GitHub App permissions.\n"
                    f"Error: {result.stderr}"
                )
            else:
                raise RuntimeError(f"Failed to clone repository: {result.stderr}")
        
        # After successful clone, reset remote URL to remove embedded credentials for security
        if self.github_app_auth and is_github_url(repo_url):
            self._reset_remote_url()
    
    def _reset_remote_url(self) -> None:
        """Reset remote URL to remove embedded credentials for security."""
        from urllib.parse import urlparse
        
        # Extract the clean repository URL
        original_url = self.task.repository_url
        parsed = urlparse(original_url)
        
        # Build clean URL without credentials
        path = parsed.path
        if not path.endswith(".git"):
            path += ".git"
        
        clean_url = f"https://{parsed.netloc}{path}"
        
        env = get_git_env()
        result = subprocess.run(
            ["git", "remote", "set-url", "origin", clean_url],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            print(f"Warning: Failed to reset remote URL: {result.stderr}")
        else:
            print(f"Reset remote URL to clean format: {clean_url}")
    
    def _detect_default_branch(self) -> str:
        """
        Detect the default branch of the repository.
        
        Returns:
            Name of the default branch (main or master)
        """
        # Configure git environment for non-interactive operation
        env = get_git_env()
        
        # Try to get the default branch from remote
        result = subprocess.run(
            ["git", "remote", "show", "origin"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "HEAD branch:" in line:
                    return line.split("HEAD branch:")[1].strip()
        
        # Fallback: check for common branch names
        result = subprocess.run(
            ["git", "branch", "-r"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode == 0:
            branches = result.stdout
            if "main" in branches:
                return "main"
            elif "master" in branches:
                return "master"
        
        # Final fallback
        return "main"
    
    def _checkout_branch(self, branch_name: str) -> None:
        """Checkout the specified branch."""
        # Configure git environment for non-interactive operation
        env = get_git_env()
        
        result = subprocess.run(
            ["git", "checkout", branch_name],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to checkout branch {branch_name}: {result.stderr}"
            )
    
    def _create_branch(self, branch_name: str) -> None:
        """Create and checkout a new branch."""
        # Configure git environment for non-interactive operation
        env = get_git_env()
        
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to create branch {branch_name}: {result.stderr}"
            )
    
    def _configure_git_author(self) -> None:
        """Configure git author and committer information for codebot."""
        if not self.github_app_auth or not self.work_dir:
            return
        
        # Try to get bot user ID, fallback to app_id with warning
        bot_user_id = self.github_app_auth.bot_user_id
        if not bot_user_id:
            # Fallback to app_id if bot_user_id retrieval failed
            app_id = self.github_app_auth.app_id
            if app_id:
                print(f"Warning: Could not retrieve bot user ID, using app ID as fallback: {app_id}")
                bot_user_id = app_id
            else:
                return
        
        bot_name = self.github_app_auth.get_bot_login()
        api_url = self.github_app_auth.api_url
        author_info = get_codebot_git_author_info(bot_user_id, bot_name, api_url)
        env = get_git_env(bot_user_id=bot_user_id, bot_name=bot_name, api_url=api_url)
        
        # Set git config user.name
        result = subprocess.run(
            ["git", "config", "user.name", author_info["author_name"]],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            print(f"Warning: Failed to set git user.name: {result.stderr}")
        
        # Set git config user.email
        result = subprocess.run(
            ["git", "config", "user.email", author_info["author_email"]],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            print(f"Warning: Failed to set git user.email: {result.stderr}")
        else:
            print(f"Configured git author: {author_info['author_name']} <{author_info['author_email']}>")
