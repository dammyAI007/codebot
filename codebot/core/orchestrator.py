"""Main orchestrator for codebot tasks."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

from codebot.claude.md_detector import get_claude_md_warning
from codebot.claude.runner import ClaudeRunner
from codebot.core.environment import EnvironmentManager
from codebot.core.github_app import GitHubAppAuth
from codebot.core.git_ops import GitOps
from codebot.core.github_pr import GitHubPR
from codebot.core.models import TaskPrompt


class Orchestrator:
    """Main orchestrator that coordinates all codebot components."""
    
    def __init__(
        self,
        task: TaskPrompt,
        work_base_dir: Path,
        github_app_auth: Optional[GitHubAppAuth] = None,
    ):
        """
        Initialize the orchestrator.
        
        Args:
            task: Task prompt with repository and task details
            work_base_dir: Base directory for creating work spaces
            github_app_auth: Optional GitHub App authentication instance (created if not provided)
        """
        self.task = task
        self.work_base_dir = work_base_dir
        
        if github_app_auth is None:
            github_app_auth = GitHubAppAuth()
        
        self.github_app_auth = github_app_auth
        
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
            
            print("\n[1/9] Task prompt parsed successfully")
            
            print("\n[2/9] Setting up environment...")
            self._setup_environment()
            
            print("\n[3/9] Checking for CLAUDE.md...")
            self._check_claude_md()
            
            print("\n[4/9] Running Claude Code CLI...")
            self._run_claude_code()
            
            print("\n[5/9] Verifying changes were committed...")
            self._verify_changes_committed()
            
            print("\n[6/9] Pushing branch to remote...")
            self._push_branch()
            
            print("\n[7/9] Creating GitHub pull request...")
            self.pr_url = self._create_pr()
            
            if self.env_manager:
                self.branch_name = self.env_manager.branch_name
            
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
        self.env_manager = EnvironmentManager(self.work_base_dir, self.task, self.github_app_auth)
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
        
        self.claude_runner = ClaudeRunner(self.work_dir, github_app_auth=self.github_app_auth)
        self.git_ops = GitOps(self.work_dir, github_app_auth=self.github_app_auth)
        
        before_commit = self.git_ops.get_latest_commit_hash()
        print(f"Repository state before Claude: {before_commit or 'No commits yet'}")
        
        append_system_prompt = None
        if self.task.test_command:
            append_system_prompt = f"Test command: {self.task.test_command}"
        
        result = self.claude_runner.run_task(
            description=self.task.description,
            append_system_prompt=append_system_prompt,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Claude Code CLI failed with exit code {result.returncode}")
        
        after_commit = self.git_ops.get_latest_commit_hash()
        
        if before_commit != after_commit:
            print(f"\n✅ Claude made changes!")
            print(f"Before: {before_commit or 'No commits'}")
            print(f"After:  {after_commit}")
            
            print("\nCleaning commit trailers...")
            self.git_ops.remove_co_author_trailers()
            
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
        
        if after_commit:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%B", after_commit],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print(f"\nCommit message:\n{result.stdout}\n")
        
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
        if not self.work_dir:
            return
        
        self.git_ops = GitOps(self.work_dir, github_app_auth=self.github_app_auth)
        
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
        if not self.env_manager or not self.env_manager.branch_name:
            return
        
        self.git_ops.push_branch(self.env_manager.branch_name)
    
    def _create_pr(self) -> Optional[str]:
        if not self.env_manager or not self.work_dir:
            return None
        
        self.github_pr = GitHubPR(self.github_app_auth)
        
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
