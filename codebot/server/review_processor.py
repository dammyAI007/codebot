"""Process PR review comments from the queue."""

import time
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

from codebot.core.environment import EnvironmentManager
from codebot.core.github_app import GitHubAppAuth
from codebot.core.git_ops import GitOps
from codebot.core.github_pr import GitHubPR
from codebot.core.models import TaskPrompt
from codebot.server.review_runner import ReviewRunner
from codebot.core.utils import extract_uuid_from_branch, find_workspace_by_uuid


class ReviewProcessor:
    """Process review comments from the queue."""
    
    def __init__(
        self,
        review_queue: Queue,
        workspace_base_dir: Path,
        github_app_auth: GitHubAppAuth,
    ):
        """
        Initialize the review processor.
        
        Args:
            review_queue: Queue containing review comments to process
            workspace_base_dir: Base directory for workspaces
            github_app_auth: GitHub App authentication instance
        """
        self.review_queue = review_queue
        self.workspace_base_dir = workspace_base_dir
        self.github_app_auth = github_app_auth
        self.github_pr = GitHubPR(github_app_auth)
        self.running = False
    
    def start(self):
        """Start processing review comments from the queue."""
        self.running = True
        print("Review processor started")
        
        while self.running:
            try:
                # Get next comment from queue (wait up to 5 seconds)
                comment_data = self.review_queue.get(timeout=5)
                
                print(f"\n{'=' * 80}")
                print(f"Processing review comment for PR #{comment_data['pr_number']}")
                print(f"{'=' * 80}\n")
                
                # Process the comment
                self.process_comment(comment_data)
                
                # Mark task as done
                self.review_queue.task_done()
                
            except Empty:
                # No items in queue, continue waiting
                continue
            except KeyboardInterrupt:
                print("\nStopping review processor...")
                self.running = False
                break
            except Exception as e:
                print(f"ERROR: Failed to process review comment: {e}")
                # Continue processing other comments
                continue
    
    def stop(self):
        """Stop the review processor."""
        self.running = False
    
    def process_comment(self, comment_data: dict):
        """
        Process a single review comment.
        
        Args:
            comment_data: Dictionary with comment information
        """
        # Extract data
        pr_number = comment_data["pr_number"]
        branch_name = comment_data.get("branch_name")
        repo_url = comment_data["repo_url"]
        repo_owner = comment_data["repo_owner"]
        repo_name = comment_data["repo_name"]
        comment_body = comment_data["comment_body"]
        comment_id = comment_data["comment_id"]
        
        # If branch_name is None (issue_comment), fetch it from PR details
        if not branch_name:
            print("Fetching branch name from PR details...")
            try:
                pr_details = self.github_pr.get_pr_details(repo_owner, repo_name, pr_number)
                branch_name = pr_details.get("head", {}).get("ref")
                if not branch_name:
                    print("ERROR: Could not determine branch name from PR")
                    return
            except Exception as e:
                print(f"ERROR: Failed to fetch PR details: {e}")
                return
        
        print(f"Branch: {branch_name}")
        print(f"Comment: {comment_body[:100]}...")
        
        # Derive workspace from branch name
        workspace_path = self._get_or_create_workspace(
            branch_name,
            repo_url,
            pr_number,
        )
        
        if not workspace_path:
            print("ERROR: Failed to setup workspace")
            return
        
        print(f"Workspace: {workspace_path}")
        
        # Get PR context
        pr_context = self._get_pr_context(repo_owner, repo_name, pr_number)
        
        # Add inline comment context if available
        if comment_data.get("comment_path"):
            pr_context["comment_file"] = comment_data.get("comment_path")
            pr_context["comment_line"] = comment_data.get("comment_line")
            pr_context["comment_diff_hunk"] = comment_data.get("comment_diff_hunk", "")
        
        # Get comment thread if this is a reply
        if comment_data.get("in_reply_to_id") or comment_data.get("type") == "review_comment":
            print("Fetching comment thread...")
            thread = self.github_pr.get_comment_thread(repo_owner, repo_name, pr_number, comment_id)
            if thread and len(thread) > 1:
                pr_context["comment_thread"] = thread
                print(f"Found {len(thread)} comments in thread")
        
        # Use Claude to classify comment
        print("\nClassifying comment with Claude...")
        classification = self._classify_comment_with_claude(comment_body, pr_context)
        
        classification_type = classification["type"]
        
        if classification_type == "ambiguous":
            print("Classification: AMBIGUOUS - Asking for clarification")
            self._post_clarification_request(
                repo_owner,
                repo_name,
                pr_number,
                comment_data.get("type", "review_comment"),
                comment_id,
                classification["clarification_question"],
            )
            return
        
        if classification_type == "appreciation":
            print("Classification: APPRECIATION - Posting quick acknowledgment")
            reply_body = "Thank you! 🙏"
            self._post_reply(
                repo_owner,
                repo_name,
                pr_number,
                comment_id,
                comment_data.get("type", "review_comment"),
                reply_body,
            )
            return
        
        if classification_type == "nitpick":
            print("Classification: NITPICK - Analyzing and responding")
            # Use Claude to analyze the nitpick and generate response
            nitpick_result = self._handle_nitpick(comment_body, pr_context)
            reply_body = nitpick_result["response"]
            self._post_reply(
                repo_owner,
                repo_name,
                pr_number,
                comment_id,
                comment_data.get("type", "review_comment"),
                reply_body,
            )
            return
        
        is_change_request = classification_type == "change_request"
        
        if is_change_request:
            print("Classification: CHANGE REQUEST")
        else:
            print("Classification: QUERY")
        
        # Run Claude Code to handle the comment
        print("\nRunning Claude Code...")
        review_runner = ReviewRunner(workspace_path, github_app_auth=self.github_app_auth)
        
        try:
            result = review_runner.handle_review_comment(
                comment_body=comment_body,
                pr_context=pr_context,
                is_change_request=is_change_request,
            )
            
            if result.returncode != 0:
                print(f"ERROR: Claude Code failed with exit code {result.returncode}")
                self._post_error_reply(
                    repo_owner,
                    repo_name,
                    comment_id,
                    comment_data["type"],
                    pr_number,
                )
                return
            
            print("Claude Code completed successfully")
            
            claude_response = review_runner.extract_response(result)
            
        except Exception as e:
            print(f"ERROR: Failed to run Claude Code: {e}")
            self._post_error_reply(
                repo_owner,
                repo_name,
                comment_id,
                comment_data["type"],
                pr_number,
            )
            return
        
        # Check if changes were made
        git_ops = GitOps(workspace_path, github_app_auth=self.github_app_auth)
        
        if is_change_request:
            try:
                # Remove Co-Authored-By trailers from commits before pushing
                print("\nCleaning commit trailers...")
                git_ops.remove_co_author_trailers()
                
                print("\nPushing changes to remote...")
                git_ops.push_branch(branch_name)
                print("Changes pushed successfully")
                
                print("\nUpdating PR description with latest changes...")
                self._update_pr_description(
                    repo_owner,
                    repo_name,
                    pr_number,
                    workspace_path,
                )
                
                if claude_response:
                    reply_body = claude_response
                else:
                    commit_hash = git_ops.get_latest_commit_hash()
                    commit_msg = git_ops.get_commit_message(commit_hash)
                    reply_body = (
                        f"✅ Changes have been made to address this review comment.\n\n"
                        f"**Commit:** {commit_hash[:7]}\n"
                        f"**Message:** {commit_msg}"
                    )
                
            except Exception as e:
                print(f"Note: No new commits to push: {e}")
                
                if claude_response:
                    reply_body = claude_response
                else:
                    reply_body = "ℹ️ I've reviewed this comment. No code changes were necessary."
        else:
            if claude_response:
                reply_body = claude_response
            else:
                reply_body = "Thank you for the question. I've reviewed this."
        
        # Post reply to the comment
        self._post_reply(
            repo_owner,
            repo_name,
            pr_number,
            comment_id,
            comment_data.get("type", "review_comment"),
            reply_body,
        )
    
    def _handle_nitpick(self, comment_body: str, pr_context: dict) -> dict:
        """
        Handle a nitpick comment by analyzing it and generating a response.
        
        Args:
            comment_body: The nitpick comment text
            pr_context: PR context information
            
        Returns:
            Dictionary with:
            - "response": The response text to post
            - "agrees": Boolean indicating if Claude agrees with the nitpick
        """
        import subprocess
        import json
        
        # Build context for the analysis
        context_parts = [
            "You received a nitpick comment on your code review.",
            "",
            "PR Context:",
            f"- Title: {pr_context.get('pr_title', 'N/A')}",
            f"- Files Changed: {pr_context.get('files_changed', 'N/A')}",
        ]
        
        if pr_context.get('comment_file'):
            context_parts.append("")
            context_parts.append("Comment Location:")
            context_parts.append(f"- File: {pr_context.get('comment_file')}")
            context_parts.append(f"- Line: {pr_context.get('comment_line')}")
            
            if pr_context.get('comment_diff_hunk'):
                context_parts.append("")
                context_parts.append("Code Being Reviewed:")
                context_parts.append("```")
                context_parts.append(pr_context.get('comment_diff_hunk'))
                context_parts.append("```")
        
        if pr_context.get('comment_thread'):
            context_parts.append("")
            context_parts.append("Comment Thread (Previous Conversation):")
            for i, thread_comment in enumerate(pr_context['comment_thread'][:-1], 1):
                author = thread_comment.get('user', {}).get('login', 'Unknown')
                body = thread_comment.get('body', '')
                context_parts.append(f"{i}. {author}: {body}")
        
        context_parts.append("")
        context_parts.append("Current Nitpick Comment:")
        context_parts.append(comment_body)
        context_parts.append("")
        
        # First, analyze the nitpick to determine if we agree
        analysis_prompt = "\n".join(context_parts) + """

Analyze this nitpick and determine if you agree with it or not. Consider:
- Is the suggestion reasonable and would it improve the code?
- Do you have a valid reason for the current implementation?
- Is this a matter of preference or an actual improvement?
- Look at the actual code being reviewed to make an informed decision

Respond ONLY with valid JSON in this exact format:
{
  "agrees": true | false,
  "reasoning": "brief explanation of why you agree or disagree"
}

Do not include any other text, markdown, or formatting. Only the JSON object."""

        try:
            result = subprocess.run(
                ["claude", "-p", analysis_prompt, "--output-format", "text"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            
            agrees = False
            reasoning = ""
            
            if result.returncode == 0 and result.stdout.strip():
                response_text = result.stdout.strip()
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    analysis = json.loads(json_str)
                    agrees = analysis.get("agrees", False)
                    reasoning = analysis.get("reasoning", "")
            
            # Generate response based on whether we agree
            if agrees:
                response = (
                    f"I agree with this suggestion! {reasoning}\n\n"
                    f"Would you like me to go ahead and make this change?"
                )
            else:
                response = (
                    f"Thanks for the suggestion! {reasoning}\n\n"
                    f"I think the current implementation works well here, but I'm happy to discuss further if you'd like."
                )
            
            return {
                "response": response,
                "agrees": agrees,
            }
            
        except Exception as e:
            print(f"Warning: Failed to generate nitpick response: {e}")
            return {
                "response": "Thanks for the feedback! I'll consider this for future improvements.",
                "agrees": False,
            }
    
    def _post_reply(
        self,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        comment_id: int,
        comment_type: str,
        reply_body: str,
    ) -> None:
        """
        Post a reply to a comment.
        
        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            pr_number: PR number
            comment_id: Comment ID to reply to
            comment_type: Type of comment ("review_comment", "issue_comment", etc.)
            reply_body: Reply text
        """
        print("\nPosting reply to GitHub...")
        try:
            if comment_type == "review_comment":
                self.github_pr.post_review_comment_reply(
                    repo_owner,
                    repo_name,
                    pr_number,
                    comment_id,
                    reply_body,
                )
            else:
                self.github_pr.post_pr_comment(
                    repo_owner,
                    repo_name,
                    pr_number,
                    reply_body,
                )
            print("Reply posted successfully")
        except Exception as e:
            print(f"ERROR: Failed to post reply: {e}")
    
    def _get_or_create_workspace(
        self,
        branch_name: str,
        repo_url: str,
        pr_number: int,
    ) -> Optional[Path]:
        """
        Get existing workspace or create a new one.
        
        Args:
            branch_name: Branch name
            repo_url: Repository URL
            pr_number: PR number
            
        Returns:
            Path to workspace or None if failed
        """
        # Try to find existing workspace by UUID
        uuid = extract_uuid_from_branch(branch_name)
        
        if uuid:
            workspace_path = find_workspace_by_uuid(self.workspace_base_dir, uuid)
            
            if workspace_path and workspace_path.exists():
                print(f"Found existing workspace: {workspace_path}")
                
                # Reuse and update workspace
                task = TaskPrompt(
                    description=f"Review comment on PR #{pr_number}",
                    repository_url=repo_url,
                )
                
                env_manager = EnvironmentManager(
                    base_dir=self.workspace_base_dir,
                    task=task,
                    github_app_auth=self.github_app_auth,
                )
                
                try:
                    env_manager.reuse_workspace(
                        workspace_path,
                        branch_name,
                        repo_url,
                    )
                    return workspace_path
                except Exception as e:
                    print(f"Warning: Failed to reuse workspace: {e}")
                    print("Will create a new workspace instead")
        
        # If no existing workspace, create a new one
        print("Creating new workspace...")
        task = TaskPrompt(
            description=f"Review comment on PR #{pr_number}",
            repository_url=repo_url,
        )
        
        env_manager = EnvironmentManager(
            base_dir=self.workspace_base_dir,
            task=task,
            github_app_auth=self.github_app_auth,
        )
        
        try:
            # Create workspace directory
            dir_name = f"task_{uuid}" if uuid else f"task_{pr_number}"
            workspace_path = self.workspace_base_dir / dir_name
            workspace_path.mkdir(parents=True, exist_ok=True)
            
            env_manager.work_dir = workspace_path
            print(f"Created work directory: {workspace_path}")
            
            # Clone repository
            env_manager._clone_repository()
            
            # Checkout the PR branch
            env_manager.branch_name = branch_name
            env_manager._checkout_branch(branch_name)
            
            return workspace_path
            
        except Exception as e:
            print(f"ERROR: Failed to create workspace: {e}")
            return None
    
    def _get_pr_context(self, owner: str, repo: str, pr_number: int) -> dict:
        """
        Get PR context for Claude.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            
        Returns:
            Dictionary with PR context
        """
        try:
            pr_details = self.github_pr.get_pr_details(owner, repo, pr_number)
            files_changed = self.github_pr.get_pr_files_changed(owner, repo, pr_number)
            
            return {
                "pr_title": pr_details.get("title", ""),
                "pr_body": pr_details.get("body", ""),
                "files_changed": files_changed,
            }
        except Exception as e:
            print(f"Warning: Failed to get PR context: {e}")
            return {
                "pr_title": "",
                "pr_body": "",
                "files_changed": "",
            }
    
    def _classify_comment_with_claude(self, comment_body: str, pr_context: dict) -> dict:
        """
        Use Claude to classify a review comment as query, change request, or ambiguous.
        
        Args:
            comment_body: Comment text
            pr_context: PR context information
            
        Returns:
            Dictionary with:
            - type: "query", "change_request", or "ambiguous"
            - clarification_question: Question to ask if ambiguous (optional)
        """
        import subprocess
        import json
        
        # Build context with code snippet if available
        context_parts = [
            "You are analyzing a code review comment to determine its intent.",
            "",
            "PR Context:",
            f"- Title: {pr_context.get('pr_title', 'N/A')}",
            f"- Files Changed: {pr_context.get('files_changed', 'N/A')}",
        ]
        
        if pr_context.get('comment_file'):
            context_parts.append("")
            context_parts.append("Comment Location:")
            context_parts.append(f"- File: {pr_context.get('comment_file')}")
            context_parts.append(f"- Line: {pr_context.get('comment_line')}")
            
            if pr_context.get('comment_diff_hunk'):
                context_parts.append("")
                context_parts.append("Code Being Reviewed:")
                context_parts.append("```")
                context_parts.append(pr_context.get('comment_diff_hunk'))
                context_parts.append("```")
        
        if pr_context.get('comment_thread'):
            context_parts.append("")
            context_parts.append("Comment Thread (Previous Conversation):")
            for i, thread_comment in enumerate(pr_context['comment_thread'][:-1], 1):
                author = thread_comment.get('user', {}).get('login', 'Unknown')
                body = thread_comment.get('body', '')
                context_parts.append(f"{i}. {author}: {body}")
            context_parts.append("")
        
        context_parts.append("")
        context_parts.append("Current Review Comment:")
        context_parts.append(comment_body)
        context_parts.append("")
        context_parts.append("Classify this comment into ONE of these categories:")
        
        classification_prompt = "\n".join(context_parts) + """

Classify this comment into ONE of these categories:

1. QUERY - The reviewer is asking a question or seeking clarification about the code
   Examples: "Why did you choose this approach?", "What does this parameter do?", "How does this work?"

2. CHANGE_REQUEST - The reviewer is requesting specific code changes
   Examples: "Please add error handling", "This should use async/await", "Remove this console.log"

3. APPRECIATION - The reviewer is expressing approval, appreciation, or positive feedback (non-blocking)
   Examples: "Looks good!", "Nice work!", "Great implementation", "Approved", "LGTM"

4. NITPICK - The reviewer is making a minor suggestion or pointing out a small issue (not a blocking change request)
   Examples: "Maybe use a more descriptive variable name?", "Consider adding a comment here", "Minor: could use const instead"

5. AMBIGUOUS - The intent is unclear and needs clarification from the reviewer
   Examples: "This could be better", "Not sure about this", "Hmm..."

Respond ONLY with valid JSON in this exact format:
{{
  "type": "query" | "change_request" | "appreciation" | "nitpick" | "ambiguous",
  "reasoning": "brief explanation of your classification",
  "clarification_question": "question to ask if ambiguous (only if type is ambiguous)"
}}

Do not include any other text, markdown, or formatting. Only the JSON object."""

        try:
            result = subprocess.run(
                ["claude", "-p", classification_prompt, "--output-format", "text"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                print(f"Warning: Claude classification failed, defaulting to query")
                return {"type": "query", "reasoning": "Classification failed"}
            
            response_text = result.stdout.strip()
            
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                classification = json.loads(json_str)
                
                print(f"Claude classification: {classification['type']}")
                print(f"Reasoning: {classification.get('reasoning', 'N/A')}")
                
                return classification
            else:
                print("Warning: Could not parse Claude response, defaulting to query")
                return {"type": "query", "reasoning": "Parse failed"}
                
        except Exception as e:
            print(f"Warning: Error during classification: {e}, defaulting to query")
            return {"type": "query", "reasoning": f"Error: {e}"}
    
    def _update_pr_description(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        workspace_path: Path,
    ):
        """
        Update PR description using Claude to generate a cohesive summary from the diff.
        """
        try:
            import subprocess
            import json
            
            pr_details = self.github_pr.get_pr_details(owner, repo, pr_number)
            pr_title = pr_details.get("title", "")
            original_body = pr_details.get("body", "")
            
            task_description = ""
            if "## 📋 Task Description" in original_body:
                start = original_body.find("## 📋 Task Description")
                end = original_body.find("## 🔨 Changes Made", start)
                if end == -1:
                    end = original_body.find("## 📁 Files Changed", start)
                if end != -1:
                    task_section = original_body[start:end].strip()
                    task_description = task_section.replace("## 📋 Task Description\n\n", "").strip()
            
            result = subprocess.run(
                ["git", "diff", "--name-only", "origin/main...HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
            )
            files_changed = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
            
            result = subprocess.run(
                ["git", "diff", "origin/main...HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
            )
            full_diff = result.stdout.strip()
            
            if len(full_diff) > 8000:
                full_diff = full_diff[:8000] + "\n\n... (diff truncated for brevity)"
            
            files_section = ""
            if len(files_changed) <= 5:
                files_section = "\n\n## 📁 Files Changed\n\n"
                for file in files_changed:
                    files_section += f"- `{file}`\n"
            
            prompt = f"""Analyze this PR and generate a concise, cohesive description of ALL changes made.

Original Task:
{task_description}

Files Changed: {', '.join(files_changed)}

Full Diff:
{full_diff}

Generate a PR description in this EXACT format (respond ONLY with the markdown, no preamble):

## 📋 Task Description

{task_description}

## 🔨 Changes Made

[Write a cohesive summary of what was implemented. Describe the changes as ONE unified implementation, not as separate commits. Focus on WHAT was built and HOW it works. Be concise but complete.]{files_section}

---
*This PR was automatically generated by [codebot](https://github.com/ajibigad/codebot) 🤖*

**CRITICAL REQUIREMENTS:**
- Write the "Changes Made" section as a unified description of the complete implementation. Do NOT list individual commits or updates. Describe the feature as it exists now.
- **DO NOT include any of the following in your response:**
  * "🤖 Generated with Claude Code" or any variation of this text
  * "Co-Authored-By:" trailers or any author attribution lines
  * Any text that mentions Claude Code or Claude as an author"""

            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "text"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if result.returncode == 0 and result.stdout.strip():
                new_body = result.stdout.strip()
                
                # Clean unwanted lines from Claude's response
                cleaned_body = self._clean_pr_description(new_body)
                
                if "## 📋 Task Description" in cleaned_body:
                    self.github_pr.update_pr_description(owner, repo, pr_number, pr_title, cleaned_body)
                    print("PR description updated successfully with Claude-generated summary")
                else:
                    print("Warning: Claude response didn't match expected format, skipping update")
            else:
                print(f"Warning: Claude failed to generate PR description")
            
        except Exception as e:
            print(f"Warning: Failed to update PR description: {e}")
    
    def _clean_pr_description(self, description: str) -> str:
        """
        Clean PR description by removing unwanted lines.

        Args:
            description: Original PR description

        Returns:
            Cleaned PR description
        """
        lines = description.split("\n")
        cleaned_lines = []

        for line in lines:
            # Skip lines that match unwanted patterns
            stripped = line.strip()
            # Remove "🤖 Generated with Claude Code" (exact match or contains)
            if stripped == "🤖 Generated with Claude Code" or "🤖 Generated with Claude Code" in stripped:
                continue
            # Remove Co-Authored-By trailers
            if stripped.startswith("Co-Authored-By:"):
                continue
            cleaned_lines.append(line)

        # Join and clean up any double newlines that might result
        cleaned = "\n".join(cleaned_lines).strip()
        # Remove any trailing empty lines
        while cleaned.endswith("\n\n"):
            cleaned = cleaned[:-1]

        return cleaned
    
    def _post_clarification_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_type: str,
        comment_id: int,
        clarification_question: str,
    ):
        """
        Post a clarification request when comment intent is ambiguous.
        """
        clarification_body = (
            f"🤔 {clarification_question}\n\n"
            f"Please clarify if you'd like me to:\n"
            f"- **Answer a question** about the code\n"
            f"- **Make specific changes** to the code"
        )
        
        try:
            if comment_type == "review_comment":
                self.github_pr.post_review_comment_reply(
                    owner,
                    repo,
                    pr_number,
                    comment_id,
                    clarification_body,
                )
            else:
                self.github_pr.post_pr_comment(
                    owner,
                    repo,
                    pr_number,
                    clarification_body,
                )
            print("Clarification request posted successfully")
        except Exception as e:
            print(f"ERROR: Failed to post clarification request: {e}")
    
    def _post_error_reply(
        self,
        owner: str,
        repo: str,
        comment_id: int,
        comment_type: str,
        pr_number: int,
    ):
        error_body = (
            "❌ I encountered an error while processing this comment.\n\n"
            "Please try again or contact the maintainers."
        )
        
        try:
            if comment_type == "review_comment":
                self.github_pr.post_review_comment_reply(
                    owner,
                    repo,
                    pr_number,
                    comment_id,
                    error_body,
                )
            else:
                self.github_pr.post_pr_comment(
                    owner,
                    repo,
                    pr_number,
                    error_body,
                )
        except Exception as e:
            print(f"ERROR: Failed to post error reply: {e}")

