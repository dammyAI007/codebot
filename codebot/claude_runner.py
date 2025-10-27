"""Claude Code CLI integration."""

import subprocess
from pathlib import Path
from typing import Optional


class ClaudeRunner:
    """Runner for Claude Code CLI in headless mode."""
    
    def __init__(self, work_dir: Path):
        """
        Initialize the Claude runner.
        
        Args:
            work_dir: Working directory where Claude Code should run
        """
        self.work_dir = work_dir
        self._check_claude_installed()
    
    def _check_claude_installed(self) -> None:
        """Check if Claude Code CLI is installed."""
        result = subprocess.run(
            ["which", "claude"],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            raise RuntimeError(
                "Claude Code CLI is not installed. "
                "Please install it from https://www.anthropic.com/claude/docs/claude-code"
            )
    
    def run_task(
        self,
        description: str,
        append_system_prompt: Optional[str] = None,
    ) -> subprocess.CompletedProcess:
        """
        Run Claude Code CLI in headless mode with the given task description.
        
        Args:
            description: The task description to give to Claude
            append_system_prompt: Optional additional system prompt instructions
            
        Returns:
            CompletedProcess with the command result
        """
        # Build the system prompt with comprehensive instructions
        system_prompt = (
            "You are a senior engineer that has been tasked to work on this task. You should do the following:\n\n"
            "1. **Read and understand the task description**\n"
            "   - Carefully analyze the requirements and scope\n"
            "   - Identify any potential challenges or dependencies\n"
            "   - Clarify any ambiguities in the task description\n\n"
            "2. **Come up with a plan**\n"
            "   - Break down the task into logical steps\n"
            "   - Consider the impact on existing code and tests\n"
            "   - Plan your approach before starting implementation\n\n"
            "3. **Implement your plan**\n"
            "   - Write clean, maintainable code following best practices\n"
            "   - Follow the project's coding standards and conventions\n"
            "   - Make incremental changes and test as you go\n\n"
            "4. **Write tests and run them to verify your changes work fine**\n"
            "   - Write comprehensive tests for new functionality\n"
            "   - Update existing tests if needed\n"
            "   - Ensure all tests pass before proceeding\n\n"
            "5. **Run all tests in the codebase to ensure you have not broken previous functionality**\n"
            "   - Execute the full test suite to verify no regressions\n"
            "   - Fix any issues that arise from your changes\n"
            "   - Ensure the codebase remains stable\n\n"
            "6. **Commit your changes with a very clear commit message highlighting the changes you made**\n"
            "   - Write descriptive commit messages that explain what was changed and why\n"
            "   - Use conventional commit format when appropriate\n"
            "   - Include relevant details about the implementation approach\n\n"
            "**Important Guidelines:**\n"
            "- Always prioritize code quality and maintainability\n"
            "- Follow the project's existing patterns and conventions\n"
            "- Consider edge cases and error handling\n"
            "- Document complex logic with clear comments\n"
            "- Ensure your changes are backward compatible when possible\n"
            "- Complete the task fully before finishing - do not leave incomplete work"
        )
        
        if append_system_prompt:
            system_prompt += f"\n\nAdditional instructions:\n{append_system_prompt}"
        
        # Build the full prompt
        full_prompt = f"Task: {description}"
        
        # Prepare command
        cmd = [
            "claude",
            "-p", full_prompt,
            "--append-system-prompt", system_prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",  # Skip permission prompts for non-interactive mode
        ]
        
        print(f"Running Claude Code CLI in headless mode...")
        print(f"Task: {description}")
        print("=" * 80)
        
        # Run Claude Code CLI with output streaming to terminal
        # Don't capture output so user can see what Claude is doing in real-time
        result = subprocess.run(
            cmd,
            cwd=self.work_dir,
            text=True,
        )
        
        print("=" * 80)
        return result
    
    def verify_changes_committed(self) -> bool:
        """
        Verify that changes have been committed by checking git status.
        
        Returns:
            True if there are no uncommitted changes, False otherwise
        """
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        
        # Check if there are any uncommitted changes
        return result.stdout.strip() == ""
    
    def get_commit_message(self) -> Optional[str]:
        """
        Get the most recent commit message.
        
        Returns:
            The most recent commit message, or None if no commits exist
        """
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        
        return None
