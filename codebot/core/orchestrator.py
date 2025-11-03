"""Main orchestrator for codebot tasks."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from codebot.claude.md_detector import get_claude_md_warning
from codebot.claude.runner import ClaudeRunner
from codebot.core.environment import EnvironmentManager
from codebot.core.git_ops import GitOps
from codebot.core.github_pr import GitHubPR
from codebot.core.models import TaskPrompt


class Orchestrator:
    """Main orchestrator that coordinates all codebot components."""
    
    def __init__(
        self,
        task: TaskPrompt,
        work_base_dir: Path,
        github_token: Optional[str] = None,
    ):
        """
        Initialize the orchestrator.
        
        Args:
            task: Task prompt with repository and task details
            work_base_dir: Base directory for creating work spaces
            github_token: Optional GitHub token (defaults to GITHUB_TOKEN env var)
        """
        self.task = task
        self.work_base_dir = work_base_dir
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        
        self.env_manager: Optional[EnvironmentManager] = None
        self.claude_runner: Optional[ClaudeRunner] = None
        self.git_ops: Optional[GitOps] = None
        self.github_pr: Optional[GitHubPR] = None
        self.work_dir: Optional[Path] = None
        self.branch_name: Optional[str] = None
        self.pr_url: Optional[str] = None
    
    def run(self) -> None:
        """Run the complete codebot workflow."""
        try:
            print("=" * 60)
            print("Codebot: Starting task execution")
            print("=" * 60)
            
            # Step 1: Parse task prompt (already done, task is passed in)
            print("\n[1/9] Task prompt parsed successfully")
            
            # Step 2: Setup environment
            print("\n[2/9] Setting up environment...")
            self._setup_environment()
            
            # Step 3: Check for CLAUDE.md
            print("\n[3/9] Checking for CLAUDE.md...")
            self._check_claude_md()
            
            # Step 4: Run Claude Code CLI
            print("\n[4/9] Running Claude Code CLI...")
            self._run_claude_code()
            
            # Step 5: Verify changes were committed
            print("\n[5/9] Verifying changes were committed...")
            self._verify_changes_committed()
            
            # Step 6: Push branch to remote
            print("\n[6/9] Pushing branch to remote...")
            self._push_branch()
            
            # Step 7: Create GitHub PR
            print("\n[7/9] Creating GitHub pull request...")
            self.pr_url = self._create_pr()
            
            # Store branch name for API access
            if self.env_manager:
                self.branch_name = self.env_manager.branch_name
            
            # Steps 8-9: Summary and cleanup
            print("\n[8-9/9] Task completed successfully!")
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            print(f"Work directory: {self.work_dir}")
            if self.branch_name:
                print(f"Branch: {self.branch_name}")
            if self.pr_url:
                print(f"Pull request: {self.pr_url}")
            print("=" * 60)
            
        except Exception as e:
            print(f"\nERROR: {e}", file=sys.stderr)
            if self.work_dir:
                print(f"\nWork directory preserved for inspection: {self.work_dir}")
            raise
    
    def _setup_environment(self) -> None:
        """Setup the isolated environment."""
        self.env_manager = EnvironmentManager(self.work_base_dir, self.task, self.github_token)
        self.work_dir = self.env_manager.setup_environment()
        print(f"Environment setup complete: {self.work_dir}")
    
    def _check_claude_md(self) -> None:
        """Check for CLAUDE.md and warn if not found."""
        if not self.work_dir:
            return
        
        warning = get_claude_md_warning(self.work_dir)
        if warning:
            print(warning)
        else:
            print("CLAUDE.md found - Claude Code will use it for context")
    
    def _run_claude_code(self) -> None:
        """Run Claude Code CLI on the task."""
        if not self.work_dir:
            return
        
        self.claude_runner = ClaudeRunner(self.work_dir)
        self.git_ops = GitOps(self.work_dir)
        
        # Capture git state before Claude runs
        before_commit = self.git_ops.get_latest_commit_hash()
        print(f"Repository state before Claude: {before_commit or 'No commits yet'}")
        
        # Add any additional instructions if needed
        append_system_prompt = None
        if self.task.test_command:
            append_system_prompt = f"Test command: {self.task.test_command}"
        
        result = self.claude_runner.run_task(
            description=self.task.description,
            append_system_prompt=append_system_prompt,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Claude Code CLI failed with exit code {result.returncode}")
        
        # Capture git state after Claude runs
        after_commit = self.git_ops.get_latest_commit_hash()
        
        if before_commit != after_commit:
            print(f"\n✅ Claude made changes!")
            print(f"Before: {before_commit or 'No commits'}")
            print(f"After:  {after_commit}")
            
            # Show what changed
            self._show_git_changes(before_commit, after_commit)
        else:
            print(f"\n⚠️  Warning: No new commits detected. Claude may not have made changes.")
        
        print("Claude Code CLI completed successfully")
    
    def _show_git_changes(self, before_commit: Optional[str], after_commit: Optional[str]) -> None:
        """Show what changed between two commits."""
        if not self.work_dir:
            return
        
        print("\n" + "=" * 80)
        print("CHANGES MADE BY CLAUDE:")
        print("=" * 80)
        
        # Show commit message
        if after_commit:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%B", after_commit],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print(f"\nCommit message:\n{result.stdout}\n")
        
        # Show files changed
        if before_commit:
            result = subprocess.run(
                ["git", "diff", "--name-status", before_commit, after_commit or "HEAD"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
            )
        else:
            result = subprocess.run(
                ["git", "show", "--name-status", "--pretty=format:", after_commit or "HEAD"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
            )
        
        if result.returncode == 0 and result.stdout.strip():
            print("Files changed:")
            print(result.stdout)
        
        # Show diff stats
        if before_commit:
            result = subprocess.run(
                ["git", "diff", "--stat", before_commit, after_commit or "HEAD"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
            )
        else:
            result = subprocess.run(
                ["git", "show", "--stat", after_commit or "HEAD"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
            )
        
        if result.returncode == 0 and result.stdout.strip():
            print(f"\n{result.stdout}")
        
        print("=" * 80 + "\n")
    
    def _verify_changes_committed(self) -> None:
        """Verify that changes were committed."""
        if not self.work_dir:
            return
        
        self.git_ops = GitOps(self.work_dir)
        
        if self.git_ops.has_uncommitted_changes():
            print("WARNING: Uncommitted changes detected")
            commit_msg = self.claude_runner.get_commit_message() if self.claude_runner else None
            if commit_msg:
                print(f"Using commit message from Claude: {commit_msg}")
                self.git_ops.commit_changes(commit_msg)
            else:
                print("Creating commit with task description")
                self.git_ops.commit_changes(self.task.description[:100])
        else:
            print("Changes already committed")
    
    def _push_branch(self) -> None:
        """Push the branch to remote."""
        if not self.env_manager or not self.env_manager.branch_name:
            return
        
        self.git_ops.push_branch(self.env_manager.branch_name)
    
    def _create_pr(self) -> Optional[str]:
        """Create GitHub pull request."""
        if not self.env_manager or not self.work_dir:
            return None
        
        self.github_pr = GitHubPR(self.github_token)
        
        # Get commit message from the latest commit
        commit_message = None
        if self.git_ops:
            commit_message = self.git_ops.get_latest_commit_hash()
            if commit_message:
                result = subprocess.run(
                    ["git", "log", "-1", "--pretty=format:%B"],
                    cwd=self.work_dir,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    commit_message = result.stdout.strip()
        
        # Get files changed
        files_changed = None
        if self.git_ops:
            result = subprocess.run(
                ["git", "diff", "--name-status", "HEAD~1", "HEAD"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                files_changed = result.stdout.strip()
        
        title = self.github_pr.generate_pr_title(self.task)
        body = self.github_pr.generate_pr_body(
            self.task,
            commit_message=commit_message,
            files_changed=files_changed,
        )
        
        pr_data = self.github_pr.create_pull_request(
            repository_url=self.task.repository_url,
            branch_name=self.env_manager.branch_name,
            base_branch=self.env_manager.default_branch or "main",
            title=title,
            body=body,
        )
        
        return pr_data.get("html_url")
