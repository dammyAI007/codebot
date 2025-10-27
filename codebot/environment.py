"""Environment manager for isolated development environments."""

import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from codebot.models import TaskPrompt
from codebot.utils import generate_branch_name, generate_directory_name, get_git_env


class EnvironmentManager:
    """Manages isolated development environments for codebot tasks."""
    
    def __init__(self, base_dir: Path, task: TaskPrompt, github_token: Optional[str] = None):
        """
        Initialize the environment manager.
        
        Args:
            base_dir: Base directory for creating temporary workspaces
            task: Task prompt containing repository and task details
            github_token: GitHub token for authentication (optional)
        """
        self.base_dir = base_dir
        self.task = task
        self.github_token = github_token
        self.work_dir: Optional[Path] = None
        self.branch_name: Optional[str] = None
        self.default_branch: Optional[str] = None
    
    def setup_environment(self) -> Path:
        """
        Setup the isolated environment by creating directory, cloning repo, and checking out branch.
        
        Returns:
            Path to the working directory
        """
        # Create work directory
        dir_name = generate_directory_name(self.task.ticket_id)
        self.work_dir = self.base_dir / dir_name
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Created work directory: {self.work_dir}")
        
        # Clone repository
        self._clone_repository()
        
        # Detect default branch
        self.default_branch = self._detect_default_branch()
        print(f"Detected default branch: {self.default_branch}")
        
        # Checkout base branch if specified, otherwise use default
        base_branch = self.task.base_branch or self.default_branch
        self._checkout_branch(base_branch)
        
        # Generate and checkout new branch
        self.branch_name = generate_branch_name(
            ticket_id=self.task.ticket_id,
            short_name=self.task.ticket_summary,
        )
        print(f"Creating branch: {self.branch_name}")
        self._create_branch(self.branch_name)
        
        return self.work_dir
    
    def _clone_repository(self) -> None:
        """Clone the repository into the work directory."""
        # Prepare repository URL with authentication if token is available
        repo_url = self.task.repository_url
        
        if self.github_token and repo_url.startswith("https://github.com/"):
            # Extract the repository path from the URL
            if repo_url.endswith(".git"):
                repo_path = repo_url[19:-4]  # Remove "https://github.com/" and ".git"
            else:
                repo_path = repo_url[19:]  # Remove "https://github.com/"
            
            # Create authenticated URL using oauth2 format (more secure than username:token)
            repo_url = f"https://oauth2:{self.github_token}@github.com/{repo_path}.git"
            print(f"Cloning repository with authentication: https://github.com/{repo_path}")
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
                    f"Authentication failed. Please check your GitHub token permissions and validity.\n"
                    f"Error: {result.stderr}"
                )
            elif "not found" in error_msg or "404" in error_msg:
                raise RuntimeError(
                    f"Repository not found or access denied. Please check the repository URL and token permissions.\n"
                    f"Error: {result.stderr}"
                )
            else:
                raise RuntimeError(f"Failed to clone repository: {result.stderr}")
        
        # After successful clone, reset remote URL to remove embedded credentials for security
        if self.github_token and repo_url.startswith("https://oauth2:"):
            self._reset_remote_url()
    
    def _reset_remote_url(self) -> None:
        """Reset remote URL to remove embedded credentials for security."""
        # Extract the clean repository path
        repo_path = self.task.repository_url
        if repo_path.endswith(".git"):
            repo_path = repo_path[19:-4]  # Remove "https://github.com/" and ".git"
        else:
            repo_path = repo_path[19:]  # Remove "https://github.com/"
        
        # Set clean remote URL without credentials
        clean_url = f"https://github.com/{repo_path}.git"
        
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
