"""Claude Code CLI integration."""

import json
import subprocess
from pathlib import Path
from typing import Optional

from codebot.core.github_app import GitHubAppAuth
from codebot.core.utils import get_codebot_git_author_info, get_git_env


class ClaudeRunner:
    """Runner for Claude Code CLI in headless mode."""
    
    def __init__(self, work_dir: Path, github_app_auth: Optional[GitHubAppAuth] = None):
        """
        Initialize the Claude runner.
        
        Args:
            work_dir: Working directory where Claude Code should run
            github_app_auth: Optional GitHub App authentication instance
        """
        self.work_dir = work_dir
        self.github_app_auth = github_app_auth
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
            "   - Include relevant details about the implementation approach\n"
            "   - **CRITICAL: DO NOT include any of the following in your commit messages:**\n"
            "     * \"🤖 Generated with Claude Code\" or any variation of this text\n"
            "     * \"Co-Authored-By:\" trailers or any author attribution lines\n"
            "     * Any text that mentions Claude Code or Claude as an author\n"
            "**Important Guidelines:**\n"
            "- Always prioritize code quality and maintainability\n"
            "- Follow the project's existing patterns and conventions\n"
            "- Consider edge cases and error handling\n"
            "- Document complex logic with clear comments\n"
            "- Ensure your changes are backward compatible when possible\n"
            "- Complete the task fully before finishing - do not leave incomplete work\n"
            "- **NEVER add \"🤖 Generated with Claude Code\" or \"Co-Authored-By:\" to commit messages**"
        )
        
        if append_system_prompt:
            system_prompt += f"\n\nAdditional instructions:\n{append_system_prompt}"
        
        full_prompt = f"Task: {description}"
        
        cmd = [
            "claude",
            "-p", full_prompt,
            "--append-system-prompt", system_prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]
        
        self._configure_git_author()
        
        print(f"Running Claude Code CLI in headless mode...")
        print(f"Task: {description}")
        print("=" * 80)
        
        git_env = self._get_git_env()
        
        result = subprocess.run(
            cmd,
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=git_env,
        )
        
        print(result.stdout)
        print("=" * 80)
        return result
    
    def _configure_git_author(self) -> None:
        """Configure git author and committer information for codebot."""
        if not self.github_app_auth or not self.work_dir:
            return
        
        bot_user_id = self.github_app_auth.bot_user_id
        if not bot_user_id:
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
        
        result = subprocess.run(
            ["git", "config", "user.name", author_info["author_name"]],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        
        if result.returncode != 0:
            print(f"Warning: Failed to set git user.name: {result.stderr}")
        
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
            print(f"Configured git author for Claude Code CLI: {author_info['author_name']} <{author_info['author_email']}>")
    
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
    
    def verify_changes_committed(self) -> bool:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        
        return result.stdout.strip() == ""
    
    def get_commit_message(self) -> Optional[str]:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        
        return None
    
    def extract_claude_response(self, result: subprocess.CompletedProcess) -> Optional[str]:
        """
        Extract Claude's text responses from the stream-json output.
        
        Args:
            result: CompletedProcess from run_task
            
        Returns:
            Final response from Claude, or None if extraction fails
        """
        if result.returncode != 0 or not result.stdout:
            return None
        
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                
                if data.get("type") == "result" and "result" in data:
                    return data["result"]
                    
            except json.JSONDecodeError:
                continue
        
        return None
