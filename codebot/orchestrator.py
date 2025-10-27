"""Main orchestrator for codebot tasks."""

import sys
from pathlib import Path
from typing import Optional

from codebot.claude_md_detector import get_claude_md_warning
from codebot.claude_runner import ClaudeRunner
from codebot.environment import EnvironmentManager
from codebot.git_ops import GitOps
from codebot.github_pr import GitHubPR
from codebot.models import TaskPrompt


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
        self.github_token = github_token
        
        self.env_manager: Optional[EnvironmentManager] = None
        self.claude_runner: Optional[ClaudeRunner] = None
        self.git_ops: Optional[GitOps] = None
        self.github_pr: Optional[GitHubPR] = None
        self.work_dir: Optional[Path] = None
    
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
            pr_url = self._create_pr()
            
            # Steps 8-9: Summary and cleanup
            print("\n[8-9/9] Task completed successfully!")
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            print(f"Work directory: {self.work_dir}")
            if self.env_manager:
                print(f"Branch: {self.env_manager.branch_name}")
            if pr_url:
                print(f"Pull request: {pr_url}")
            print("=" * 60)
            
        except Exception as e:
            print(f"\nERROR: {e}", file=sys.stderr)
            if self.work_dir:
                print(f"\nWork directory preserved for inspection: {self.work_dir}")
            raise
    
    def _setup_environment(self) -> None:
        """Setup the isolated environment."""
        self.env_manager = EnvironmentManager(self.work_base_dir, self.task)
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
        
        # Add any additional instructions if needed
        append_system_prompt = None
        if self.task.test_command:
            append_system_prompt = f"Test command: {self.task.test_command}"
        
        result = self.claude_runner.run_task(
            description=self.task.description,
            append_system_prompt=append_system_prompt,
        )
        
        if result.returncode != 0:
            print("Claude Code CLI output:", file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            raise RuntimeError(f"Claude Code CLI failed with exit code {result.returncode}")
        
        print("Claude Code CLI completed successfully")
    
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
        if not self.env_manager:
            return None
        
        self.github_pr = GitHubPR(self.github_token)
        
        title = self.github_pr.generate_pr_title(self.task)
        body = self.github_pr.generate_pr_body(self.task)
        
        pr_data = self.github_pr.create_pull_request(
            repository_url=self.task.repository_url,
            branch_name=self.env_manager.branch_name,
            base_branch=self.env_manager.default_branch or "main",
            title=title,
            body=body,
        )
        
        return pr_data.get("html_url")
