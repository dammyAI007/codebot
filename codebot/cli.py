"""CLI interface for codebot."""

import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from codebot.orchestrator import Orchestrator
from codebot.parser import parse_task_prompt, parse_task_prompt_file


@click.command()
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
def main(
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
    # Load environment variables from .env file
    load_dotenv()

    import pdb; pdb.set_trace()
    
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
    
    # Create and run orchestrator
    try:
        orchestrator = Orchestrator(
            task=task,
            work_base_dir=work_base_dir,
            github_token=github_token,
        )
        orchestrator.run()
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        if verbose:
            import traceback
            click.echo(f"\nError details:", err=True)
            traceback.print_exc()
        click.echo(f"\nError: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
