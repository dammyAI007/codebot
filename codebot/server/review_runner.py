"""Claude Code runner specialized for handling PR review comments."""

import subprocess
from pathlib import Path
from typing import Optional

from codebot.claude.runner import ClaudeRunner
from codebot.core.github_app import GitHubAppAuth


class ReviewRunner:
    """Runner for Claude Code CLI specialized for PR review comments."""
    
    def __init__(self, work_dir: Path, github_app_auth: Optional[GitHubAppAuth] = None):
        """
        Initialize the review runner.
        
        Args:
            work_dir: Working directory where Claude Code should run
            github_app_auth: Optional GitHub App authentication instance
        """
        self.work_dir = work_dir
        self.claude_runner = ClaudeRunner(work_dir, github_app_auth=github_app_auth)
    
    def handle_review_comment(
        self,
        comment_body: str,
        pr_context: dict,
        is_change_request: bool = False,
    ) -> subprocess.CompletedProcess:
        """
        Handle a PR review comment using Claude Code.
        
        Args:
            comment_body: The review comment text
            pr_context: Dictionary with PR context (title, description, files_changed)
            is_change_request: Whether this is a change request or query
            
        Returns:
            CompletedProcess with the command result
        """
        system_prompt = self._build_review_system_prompt(
            comment_body,
            pr_context,
            is_change_request
        )
        
        if is_change_request:
            task_description = (
                f"Code Review Change Request:\n\n"
                f"{comment_body}\n\n"
                f"Please make the requested changes, test them, and commit with a clear message.\n\n"
                f"IMPORTANT: After completing the changes, provide a CONCISE summary in this format:\n"
                f"✅ [Brief statement of what was done]\n\n"
                f"**Changes:**\n"
                f"- [Change 1]\n"
                f"- [Change 2]\n\n"
                f"**Results:** [Brief test results]\n\n"
                f"Keep it short and scannable. Skip pleasantries like 'Perfect!' or 'Here's what I did'."
            )
        else:
            task_description = (
                f"Code Review Query:\n\n"
                f"{comment_body}\n\n"
                f"Please provide a clear, concise, but sufficient answer. "
                f"Be direct and to the point while ensuring the reviewer understands. "
                f"Do not make any code changes."
            )
        
        return self.claude_runner.run_task(
            description=task_description,
            append_system_prompt=system_prompt,
        )
    
    def extract_response(self, result: subprocess.CompletedProcess) -> Optional[str]:
        """
        Extract Claude's response from the result.
        
        Args:
            result: CompletedProcess from handle_review_comment
            
        Returns:
            Claude's text response, or None if extraction fails
        """
        return self.claude_runner.extract_claude_response(result)
    
    def _build_review_system_prompt(
        self,
        comment_body: str,
        pr_context: dict,
        is_change_request: bool,
    ) -> str:
        """
        Build a specialized system prompt for code review responses.
        
        Args:
            comment_body: The review comment
            pr_context: PR context information
            is_change_request: Whether this is a change request
            
        Returns:
            System prompt string
        """
        prompt_parts = []
        
        # Context about the review
        prompt_parts.append("=" * 80)
        prompt_parts.append("CODE REVIEW CONTEXT")
        prompt_parts.append("=" * 80)
        prompt_parts.append("")
        prompt_parts.append("You are responding to a code review comment on a pull request.")
        prompt_parts.append("")
        
        # PR information
        if pr_context.get("pr_title"):
            prompt_parts.append(f"PR Title: {pr_context['pr_title']}")
        
        if pr_context.get("pr_body"):
            prompt_parts.append(f"\nOriginal Task Description:")
            prompt_parts.append(pr_context['pr_body'])
        
        if pr_context.get("files_changed"):
            prompt_parts.append(f"\nFiles Changed in This PR:")
            prompt_parts.append("```")
            prompt_parts.append(pr_context['files_changed'])
            prompt_parts.append("```")
        
        if pr_context.get("comment_file"):
            prompt_parts.append(f"\nComment Location:")
            prompt_parts.append(f"- File: {pr_context.get('comment_file')}")
            prompt_parts.append(f"- Line: {pr_context.get('comment_line')}")
            
            if pr_context.get("comment_diff_hunk"):
                prompt_parts.append(f"\nCode Being Reviewed:")
                prompt_parts.append("```")
                prompt_parts.append(pr_context.get('comment_diff_hunk'))
                prompt_parts.append("```")
        
        if pr_context.get("comment_thread"):
            prompt_parts.append("")
            prompt_parts.append("=" * 80)
            prompt_parts.append("COMMENT THREAD (Previous Conversation)")
            prompt_parts.append("=" * 80)
            for i, thread_comment in enumerate(pr_context['comment_thread'][:-1], 1):
                author = thread_comment.get('user', {}).get('login', 'Unknown')
                body = thread_comment.get('body', '')
                prompt_parts.append(f"\n{i}. {author}:")
                prompt_parts.append(body)
        
        prompt_parts.append("")
        prompt_parts.append("=" * 80)
        prompt_parts.append("CURRENT REVIEW COMMENT")
        prompt_parts.append("=" * 80)
        prompt_parts.append("")
        prompt_parts.append(comment_body)
        prompt_parts.append("")
        prompt_parts.append("=" * 80)
        
        # Instructions based on comment type
        if is_change_request:
            prompt_parts.append("")
            prompt_parts.append("This is a CHANGE REQUEST. You should:")
            prompt_parts.append("1. Understand what changes are being requested")
            prompt_parts.append("2. Make the necessary code changes")
            prompt_parts.append("3. Test the changes to ensure they work")
            prompt_parts.append("4. Run all tests to ensure nothing is broken")
            prompt_parts.append("5. Commit the changes with a clear message")
            prompt_parts.append("")
            prompt_parts.append("**CRITICAL COMMIT MESSAGE REQUIREMENTS:**")
            prompt_parts.append("- Your commit message should reference that this addresses a review comment")
            prompt_parts.append("- **DO NOT include any of the following in your commit messages:**")
            prompt_parts.append("  * \"🤖 Generated with Claude Code\" or any variation of this text")
            prompt_parts.append("  * \"Co-Authored-By:\" trailers or any author attribution lines")
            prompt_parts.append("  * Any text that mentions Claude Code or Claude as an author")
            prompt_parts.append("")
            prompt_parts.append("RESPONSE FORMAT:")
            prompt_parts.append("Provide a CONCISE, scannable summary. NO pleasantries or preambles.")
            prompt_parts.append("Format:")
            prompt_parts.append("✅ [One-line summary of what was done]")
            prompt_parts.append("")
            prompt_parts.append("**Changes:**")
            prompt_parts.append("- [Specific change 1]")
            prompt_parts.append("- [Specific change 2]")
            prompt_parts.append("")
            prompt_parts.append("**Results:** [Brief test/verification results]")
        else:
            prompt_parts.append("")
            prompt_parts.append("This is a QUERY/QUESTION. You should:")
            prompt_parts.append("1. Understand what is being asked")
            prompt_parts.append("2. Provide a CONCISE but SUFFICIENT answer")
            prompt_parts.append("3. Be direct and to the point")
            prompt_parts.append("4. Reference specific code or files if relevant")
            prompt_parts.append("5. DO NOT make any code changes")
            prompt_parts.append("")
            prompt_parts.append("IMPORTANT: Keep your answer brief and focused. Avoid unnecessary elaboration.")
            prompt_parts.append("Your response will be posted as a comment reply.")
        
        return "\n".join(prompt_parts)

