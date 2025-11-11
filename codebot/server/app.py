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
@click.option(
    "--enable-polling",
    is_flag=True,
    default=False,
    help="Enable polling mode instead of webhooks (mutually exclusive with webhooks)",
)
@click.option(
    "--poll-interval",
    type=int,
    default=None,
    help="Poll interval in seconds (default: 300 or CODEBOT_POLL_INTERVAL env var)",
)
@click.option(
    "--reset-poll-times",
    is_flag=True,
    default=False,
    help="Reset poll times for all pending_review PRs to start from PR creation time",
)
def serve(
    port: int,
    work_dir: str,
    webhook_secret: str,
    debug: bool,
    api_key: str,
    workers: int,
    enable_polling: bool,
    poll_interval: int,
    reset_poll_times: bool,
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
    
    # Get poll interval
    effective_poll_interval = poll_interval
    if effective_poll_interval is None:
        poll_interval_env = os.getenv("CODEBOT_POLL_INTERVAL")
        if poll_interval_env:
            try:
                effective_poll_interval = int(poll_interval_env)
            except ValueError:
                click.echo("Warning: Invalid CODEBOT_POLL_INTERVAL, using default 300", err=True)
                effective_poll_interval = 300
        else:
            effective_poll_interval = 300
    
    # Handle polling vs webhook mode
    if enable_polling:
        # Polling mode: ignore webhook secrets completely
        print(f"Polling mode enabled (interval: {effective_poll_interval}s)")
        # Clear webhook secret from environment to ensure webhook endpoint is disabled
        if "GITHUB_WEBHOOK_SECRET" in os.environ:
            del os.environ["GITHUB_WEBHOOK_SECRET"]
    else:
        # Webhook mode: require webhook secret
        effective_secret = webhook_secret or os.getenv("GITHUB_WEBHOOK_SECRET")
        
        if not effective_secret:
            click.echo("Error: Webhook secret is required when not using polling. Set GITHUB_WEBHOOK_SECRET env var, use --webhook-secret, or use --enable-polling", err=True)
            sys.exit(1)
        
        # Set webhook secret in environment for the server
        os.environ["GITHUB_WEBHOOK_SECRET"] = effective_secret
        print("Webhook mode enabled")
    
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
    if not enable_polling:
        print(f"Webhook endpoint: http://localhost:{port}/webhook")
    else:
        print(f"Polling mode: checking PRs every {effective_poll_interval}s")
    
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
    # Only start in child process when using Flask reloader (debug mode)
    # WERKZEUG_RUN_MAIN is set to 'true' in the child process
    review_processor = None
    review_processor_thread = None
    if debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        # Parent process - skip starting review processor
        pass
    else:
        # Child process or not using reloader - start review processor
        review_processor = ReviewProcessor(
            review_queue=review_queue,
            workspace_base_dir=work_base_dir,
            github_app_auth=github_app_auth,
        )
        
        review_processor_thread = threading.Thread(target=review_processor.start, daemon=True)
        review_processor_thread.start()
    
    # Create and start poller if polling is enabled
    # Only start in child process when using Flask reloader (debug mode)
    # WERKZEUG_RUN_MAIN is set to 'true' in the child process
    poller = None
    poller_thread = None
    if enable_polling:
        werkzeug_main = os.environ.get('WERKZEUG_RUN_MAIN')
        # In debug mode with reloader, only start poller in child process
        if debug and werkzeug_main != 'true':
            # Parent process - skip starting poller
            print(f"Skipping poller start in parent process (WERKZEUG_RUN_MAIN={werkzeug_main})")
        else:
            # Child process or not using reloader - start poller
            print(f"Starting poller (debug={debug}, WERKZEUG_RUN_MAIN={werkzeug_main})")
            from codebot.server.poller import GitHubPoller
            
            poller = GitHubPoller(
                review_queue=review_queue,
                workspace_base_dir=work_base_dir,
                github_app_auth=github_app_auth,
                poll_interval=effective_poll_interval,
                reset_poll_times=reset_poll_times,
            )
            
            poller_thread = threading.Thread(target=poller.start, daemon=True)
            poller_thread.start()
    
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
    
    # Get bot login for comment detection
    bot_login = github_app_auth.get_bot_login()
    
    # Create Flask app (disable webhook endpoint if polling is enabled)
    app = create_app(
        task_queue=task_queue,
        bot_login=bot_login,
        workspace_base_dir=work_base_dir,
        github_app_auth=github_app_auth,
        enable_webhook=not enable_polling,
    )
    
    # Start Flask server (blocking)
    try:
        start_server(app, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        if review_processor:
            review_processor.stop()
        if poller:
            poller.stop()
        if task_processor:
            task_processor.stop()
        sys.exit(0)

