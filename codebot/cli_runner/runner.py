"""CLI runner for executing tasks."""

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv

from codebot.core.github_app import GitHubAppAuth
from codebot.core.models import Task
from codebot.core.orchestrator import Orchestrator
from codebot.core.parser import parse_task_prompt, parse_task_prompt_file
from codebot.core.task_store import global_task_store
from codebot.core.utils import validate_github_app_config


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
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
def run(
    task_prompt: str,
    task_prompt_file: str,
    work_dir: str,
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
    
    # Validate GitHub App configuration
    print("Validating GitHub App configuration...")
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
    
    is_valid, error_type = validate_github_app_config(repository_url=task.repository_url, verbose=verbose)
    if not is_valid:
        if error_type == "config_missing":
            click.echo("Error: GitHub App configuration not found. Please set the required environment variables.", err=True)
            click.echo("Required environment variables:", err=True)
            click.echo("  - GITHUB_APP_ID", err=True)
            click.echo("  - GITHUB_APP_PRIVATE_KEY_PATH", err=True)
            click.echo("  - GITHUB_APP_INSTALLATION_ID", err=True)
        elif error_type == "installation_not_found":
            click.echo("Error: GitHub App installation not found (404).", err=True)
            click.echo("This usually means:", err=True)
            click.echo("  1. The GITHUB_APP_INSTALLATION_ID is incorrect", err=True)
            click.echo("  2. The GitHub App is not installed on the target repositories", err=True)
            click.echo("  3. The API URL is incorrect (check GITHUB_ENTERPRISE_URL if using GitHub Enterprise)", err=True)
            click.echo("", err=True)
            click.echo("To find your installation ID:", err=True)
            click.echo("  - Check the GitHub App installation URL: https://github.com/settings/installations/<ID>", err=True)
            click.echo("  - Or use the API: curl -H 'Authorization: Bearer <JWT>' https://api.github.com/app/installations", err=True)
        else:
            click.echo(f"Error: Invalid GitHub App configuration: {error_type}", err=True)
            click.echo("Please check your configuration and try again.", err=True)
        
        if verbose:
            click.echo("", err=True)
            click.echo("Run with --verbose flag for detailed debugging information", err=True)
        sys.exit(1)
    print("GitHub App configuration validated successfully")
    
    # Create GitHub App auth instance
    github_app_auth = GitHubAppAuth()
    
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
            github_app_auth=github_app_auth,
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

