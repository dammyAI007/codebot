"""Server app for handling webhooks and HTTP requests."""

import os
import sys
import threading
from pathlib import Path

import click
from dotenv import load_dotenv

from codebot.core.github_app import GitHubAppAuth
from codebot.core.utils import validate_github_app_config


@click.command(name="serve")
@click.option(
    "--port",
    type=int,
    default=5000,
    help="Port to run webhook server on (default: 5000)",
)
@click.option(
    "--work-dir",
    type=click.Path(),
    default=None,
    help="Base directory for work spaces (defaults to ./codebot_workspace)",
)
@click.option(
    "--webhook-secret",
    type=str,
    default=None,
    help="GitHub webhook secret (defaults to GITHUB_WEBHOOK_SECRET env var or .env file)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode (auto-reload on code changes, detailed errors)",
)
@click.option(
    "--api-key",
    type=str,
    default=None,
    help="API key for HTTP endpoints (defaults to CODEBOT_API_KEYS env var)",
)
@click.option(
    "--workers",
    type=int,
    default=1,
    help="Number of task processor worker threads (default: 1)",
)
def serve(
    port: int,
    work_dir: str,
    webhook_secret: str,
    debug: bool,
    api_key: str,
    workers: int,
) -> None:
    """
    Start webhook server to handle PR review comments, HTTP task submissions, and web interface.
    
    This command starts a Flask server that:
    - Provides a web interface for viewing and managing tasks (CLI and web-initiated)
    - Listens for GitHub webhook events for PR review comments
    - Provides HTTP API endpoints for task submission
    
    Example:
        codebot serve --port 5000 --workers 2
    
    Web Interface:
    - Access at http://localhost:PORT/
    - Set CODEBOT_WEB_USERNAME and CODEBOT_WEB_PASSWORD env vars for authentication
    - View all tasks, filter by status/source, and see task details
    
    Before running, configure GitHub App credentials:
    - Set GITHUB_APP_ID environment variable
    - Set GITHUB_APP_PRIVATE_KEY_PATH environment variable (path to private key file)
    - Set GITHUB_APP_INSTALLATION_ID environment variable
    
    Before running, configure a GitHub webhook:
    1. Go to repository Settings > Webhooks
    2. Add webhook URL: https://your-server.com/webhook
    3. Content type: application/json
    4. Secret: Set GITHUB_WEBHOOK_SECRET env var
    5. Events: Select "Issue comments", "Pull request reviews", and "Pull request review comments"
    
    For HTTP API:
    - Set CODEBOT_API_KEYS environment variable with comma-separated API keys
    - Use --workers to scale task processing
    """
    load_dotenv()
    
    # Validate GitHub App configuration
    print("Validating GitHub App configuration...")
    is_valid, error_type = validate_github_app_config(verbose=True)
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
        sys.exit(1)
    print("GitHub App configuration validated successfully")
    
    # Create GitHub App auth instance
    github_app_auth = GitHubAppAuth()
    
    # Get webhook secret
    effective_secret = webhook_secret or os.getenv("GITHUB_WEBHOOK_SECRET")
    
    if not effective_secret:
        click.echo("Error: Webhook secret is required. Set GITHUB_WEBHOOK_SECRET env var or use --webhook-secret", err=True)
        sys.exit(1)
    
    # Set webhook secret in environment for the server
    os.environ["GITHUB_WEBHOOK_SECRET"] = effective_secret
    
    # Handle API keys
    if api_key:
        os.environ["CODEBOT_API_KEYS"] = api_key
    
    # Check if API is enabled
    from codebot.server.config import config
    api_enabled = config.has_api_keys()
    
    if api_enabled:
        print(f"HTTP API enabled with {len(config.api_keys)} API key(s)")
    else:
        print("HTTP API disabled (no API keys configured)")
    
    # Determine work directory
    if work_dir:
        work_base_dir = Path(work_dir)
    else:
        work_base_dir = Path.cwd() / "codebot_workspace"
    
    work_base_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Starting server on port {port}...")
    print(f"Work directory: {work_base_dir}")
    print(f"Web interface: http://localhost:{port}/")
    print(f"Health check: http://localhost:{port}/health")
    print(f"Webhook endpoint: http://localhost:{port}/webhook")
    
    if api_enabled:
        print(f"API endpoints: http://localhost:{port}/api/tasks/submit")
        print(f"               http://localhost:{port}/api/tasks/{{task_id}}/status")
        print(f"               http://localhost:{port}/api/tasks")
    
    print("\nPress Ctrl+C to stop the server\n")
    
    # Import here to avoid loading Flask unless needed
    from codebot.server.webhook import review_queue
    from codebot.server.review_processor import ReviewProcessor
    from codebot.server.task_queue import TaskQueue
    from codebot.server.task_processor import TaskProcessor
    from codebot.server.flask_app import create_app, start_server
    
    # Create and start review processor in background thread
    review_processor = ReviewProcessor(
        review_queue=review_queue,
        workspace_base_dir=work_base_dir,
        github_app_auth=github_app_auth,
    )
    
    review_processor_thread = threading.Thread(target=review_processor.start, daemon=True)
    review_processor_thread.start()
    
    # Create task queue and processor if API is enabled
    task_processor = None
    task_queue = None
    if api_enabled:
        # Create task queue
        task_queue = TaskQueue(max_size=config.max_queue_size)
        
        # Create and start task processor
        task_processor = TaskProcessor(
            task_queue=task_queue,
            workspace_base_dir=work_base_dir,
            github_app_auth=github_app_auth,
            num_workers=workers,
        )
        task_processor.start()
    
    # Create Flask app
    app = create_app(task_queue=task_queue)
    
    # Start Flask server (blocking)
    try:
        start_server(app, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        review_processor.stop()
        if task_processor:
            task_processor.stop()
        sys.exit(0)

