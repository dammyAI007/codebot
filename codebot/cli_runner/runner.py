"""CLI runner for executing tasks."""

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv

from codebot.core.models import Task
from codebot.core.orchestrator import Orchestrator
from codebot.core.parser import parse_task_prompt, parse_task_prompt_file
from codebot.core.utils import validate_github_token
from codebot.server.task_store import global_task_store


@click.command(name="run")
@click.option(
    "--task-prompt",
    type=str,
    help="Task prompt as JSON or YAML string",
)
@click.option(
    "--task-prompt-file",
    type=click.Path(exists=True),
    help="Path to task prompt file (JSON or YAML)",
)
@click.option(
    "--work-dir",
    type=click.Path(),
    default=None,
    help="Base directory for work spaces (defaults to ./codebot_workspace)",
)
@click.option(
    "--github-token",
    type=str,
    default=None,
    help="GitHub token (defaults to GITHUB_TOKEN env var or .env file)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
def run(
    task_prompt: str,
    task_prompt_file: str,
    work_dir: str,
    github_token: str,
    verbose: bool,
) -> None:
    """
    Codebot CLI - AI-assisted development task automation.
    
    This tool accepts task prompts, clones repositories, runs Claude Code CLI,
    and creates GitHub pull requests.
    
    Example:
        codebot --task-prompt-file task.yaml
    
    Example task prompt (YAML):
        repository_url: https://github.com/user/repo.git
        ticket_id: PROJ-123
        ticket_summary: fix-login-bug
        description: |
          Fix the login authentication bug.
          Ensure all tests pass.
    """
    load_dotenv()
    
    # Parse task prompt
    try:
        if task_prompt:
            task = parse_task_prompt(task_prompt)
        elif task_prompt_file:
            task = parse_task_prompt_file(task_prompt_file)
        else:
            click.echo("Error: Either --task-prompt or --task-prompt-file must be provided", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error parsing task prompt: {e}", err=True)
        sys.exit(1)
    
    # Determine work directory
    if work_dir:
        work_base_dir = Path(work_dir)
    else:
        work_base_dir = Path.cwd() / "codebot_workspace"
    
    work_base_dir.mkdir(parents=True, exist_ok=True)
    
    # Get GitHub token from flag, environment variable, or .env file
    effective_token = github_token or os.getenv("GITHUB_TOKEN")
    
    # Validate GitHub token if available
    if effective_token:
        print("Validating GitHub token...")
        if verbose:
            print("Debug information:")
            # Show environment variables that affect GitHub API detection
            github_api_url = os.getenv("GITHUB_API_URL")
            github_enterprise_url = os.getenv("GITHUB_ENTERPRISE_URL")
            if github_api_url:
                print(f"  → GITHUB_API_URL: {github_api_url}")
            if github_enterprise_url:
                print(f"  → GITHUB_ENTERPRISE_URL: {github_enterprise_url}")
            if not github_api_url and not github_enterprise_url:
                print("  → No GitHub Enterprise environment variables set, using github.com")
            print(f"  → Repository URL from task: {task.repository_url}")
        
        if not validate_github_token(effective_token, repository_url=task.repository_url, verbose=verbose):
            click.echo("Error: Invalid GitHub token. Please check your token and try again.", err=True)
            click.echo("Make sure your token has the correct permissions (repo access for private repos).", err=True)
            click.echo("", err=True)
            click.echo("Troubleshooting tips:", err=True)
            click.echo("1. Verify your token hasn't expired", err=True)
            click.echo("2. Check that your token has 'repo' scope for private repositories", err=True)
            click.echo("3. For GitHub Enterprise, ensure you're using the enterprise token", err=True)
            
            # Show the correct API URL for manual testing
            from codebot.core.utils import detect_github_api_url
            api_url = detect_github_api_url(repository_url=task.repository_url)
            click.echo(f"4. Test your token manually: curl -H 'Authorization: token YOUR_TOKEN' {api_url}/user", err=True)
            
            if verbose:
                click.echo("5. Run with --verbose flag for detailed debugging information", err=True)
            sys.exit(1)
        print("GitHub token validated successfully")
    else:
        print("Warning: No GitHub token found. This may cause issues with private repositories.")
    
    # Create task tracking object
    task_id = str(uuid.uuid4())
    task_obj = Task(
        id=task_id,
        prompt=task,
        status="pending",
        submitted_at=datetime.utcnow(),
        source="cli",
    )
    global_task_store.add_task(task_obj)
    
    # Create and run orchestrator
    try:
        global_task_store.update_task(task_id, status="running", started_at=datetime.utcnow())
        
        orchestrator = Orchestrator(
            task=task,
            work_base_dir=work_base_dir,
            github_token=effective_token,
        )
        orchestrator.run()
        
        # Task completed successfully
        result = {
            "pr_url": orchestrator.pr_url,
            "branch_name": orchestrator.branch_name,
            "work_dir": str(orchestrator.work_dir) if orchestrator.work_dir else None,
        }
        global_task_store.update_task(
            task_id,
            status="completed",
            completed_at=datetime.utcnow(),
            result=result,
        )
        
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user", err=True)
        global_task_store.update_task(
            task_id,
            status="failed",
            completed_at=datetime.utcnow(),
            error="Interrupted by user",
        )
        sys.exit(1)
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        global_task_store.update_task(
            task_id,
            status="failed",
            completed_at=datetime.utcnow(),
            error=str(e),
        )
        sys.exit(1)

