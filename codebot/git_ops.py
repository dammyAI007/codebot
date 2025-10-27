"""Git operations for committing and pushing changes."""

import subprocess
from pathlib import Path
from typing import Optional


class GitOps:
    """Git operations for codebot."""
    
    def __init__(self, work_dir: Path):
        """
        Initialize git operations.
        
        Args:
            work_dir: Working directory with git repository
        """
        self.work_dir = work_dir
    
    def commit_changes(self, message: str) -> None:
        """
        Commit all changes with the given message.
        
        Args:
            message: Commit message
        """
        # Stage all changes
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to stage changes: {result.stderr}")
        
        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
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
        # Push branch to remote
        result = subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to push branch: {result.stderr}")
        
        print(f"Pushed branch {branch_name} to remote")
    
    def has_uncommitted_changes(self) -> bool:
        """
        Check if there are uncommitted changes.
        
        Returns:
            True if there are uncommitted changes, False otherwise
        """
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        
        return result.stdout.strip() != ""
    
    def get_latest_commit_hash(self) -> Optional[str]:
        """
        Get the hash of the latest commit.
        
        Returns:
            Commit hash or None if no commits exist
        """
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
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
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        
        return None
