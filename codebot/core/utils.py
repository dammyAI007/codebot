"""Utility functions for codebot."""

import hashlib
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from codebot.core.task_store import global_task_store


def validate_github_app_config(api_url: Optional[str] = None, repository_url: Optional[str] = None, verbose: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate GitHub App configuration by testing authentication.
    
    Args:
        api_url: Optional API URL (auto-detected if not provided)
        repository_url: Optional repository URL to derive API URL from
        verbose: Enable verbose logging for debugging
        
    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    from codebot.core.github_app import GitHubAppAuth
    import requests
    
    try:
        if not api_url:
            api_url = detect_github_api_url(repository_url=repository_url, verbose=verbose)
        
        if verbose:
            print(f"  → Using API URL: {api_url}")
            print("  → Validating GitHub App configuration...")
        
        github_app_auth = GitHubAppAuth(api_url=api_url)
        
        if verbose:
            print("  → GitHub App configuration loaded successfully")
            print("  → Testing authentication by getting installation token...")
        
        token = github_app_auth.get_installation_token()
        
        if verbose:
            print(f"  → Installation token obtained successfully (starts with: {token[:8]}...)")
            print("  → GitHub App configuration is valid")
        
        # If we can get the installation token, the configuration is valid
        # The token itself will be validated when making actual API calls
        return True, None
    except RuntimeError as e:
        error_msg = str(e)
        if verbose:
            print(f"  → Configuration error: {error_msg}")
        
        # Check if it's a "not found" error (missing env vars) vs API error
        if "not found" in error_msg.lower() and ("GITHUB_APP" in error_msg or "environment variable" in error_msg):
            return False, "config_missing"
        elif "404" in error_msg or "Not Found" in error_msg:
            return False, "installation_not_found"
        else:
            return False, error_msg
    except requests.RequestException as e:
        if verbose:
            print(f"  → Request failed with exception: {type(e).__name__}: {str(e)}")
        return False, "api_error"


def detect_github_info(repository_url: str) -> Dict[str, str]:
    """
    Detect GitHub instance information from repository URL.
    
    Args:
        repository_url: Git repository URL
        
    Returns:
        Dictionary with host, is_enterprise, api_url, and base_url
    """
    parsed = urlparse(repository_url)
    
    if not parsed.netloc:
        raise ValueError(f"Invalid repository URL: {repository_url}")
    
    # Extract host
    host = parsed.netloc
    
    # Determine if it's GitHub.com or Enterprise
    is_enterprise = host != "github.com"
    
    # Build API URL
    if is_enterprise:
        api_url = f"https://{host}/api/v3"
    else:
        api_url = "https://api.github.com"
    
    return {
        "host": host,
        "is_enterprise": str(is_enterprise).lower(),
        "api_url": api_url,
        "base_url": f"https://{host}"
    }


def detect_github_api_url(repository_url: Optional[str] = None, verbose: bool = False) -> str:
    """
    Detect GitHub API URL from environment or repository URL.
    
    Args:
        repository_url: Optional repository URL to derive API from
        verbose: Enable verbose logging for debugging
        
    Returns:
        GitHub API URL
    """
    if verbose:
        print("  → Detecting GitHub API URL...")
        
    # Check explicit API URL from environment
    api_url = os.getenv("GITHUB_API_URL")
    if api_url:
        if verbose:
            print(f"  → Found GITHUB_API_URL environment variable: {api_url}")
        return api_url.rstrip("/")
    
    # Check enterprise URL from environment
    enterprise_url = os.getenv("GITHUB_ENTERPRISE_URL")
    if enterprise_url:
        api_url = f"{enterprise_url.rstrip('/')}/api/v3"
        if verbose:
            print(f"  → Found GITHUB_ENTERPRISE_URL environment variable: {enterprise_url}")
            print(f"  → Derived API URL: {api_url}")
        return api_url
    
    # Try to derive from repository URL
    if repository_url:
        if verbose:
            print(f"  → Deriving API URL from repository URL: {repository_url}")
        github_info = detect_github_info(repository_url)
        api_url = github_info["api_url"]
        if verbose:
            print(f"  → Derived API URL: {api_url}")
        return api_url
    
    # Default to github.com
    if verbose:
        print("  → No environment variables or repository URL provided, using default: https://api.github.com")
    return "https://api.github.com"


def is_github_url(url: str) -> bool:
    """
    Check if URL is a GitHub URL (github.com or enterprise).
    
    Args:
        url: Repository URL to check
        
    Returns:
        True if URL appears to be a GitHub repository
    """
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ["http", "https"] and
            parsed.netloc and
            "github" in parsed.netloc.lower()
        )
    except Exception:
        return False


def get_codebot_git_author_info(bot_user_id: str, bot_name: Optional[str] = None, api_url: Optional[str] = None) -> Dict[str, str]:
    """
    Get git author and committer information for codebot.
    
    Args:
        bot_user_id: GitHub App bot user ID (not app ID)
        bot_name: Bot name (required, must be set via GITHUB_BOT_NAME env var)
        api_url: GitHub API URL to determine the correct email domain
        
    Returns:
        Dictionary with author name, author email, committer name, and committer email
        
    Raises:
        ValueError: If bot_name is not provided
    """
    if not bot_name:
        raise ValueError("Bot name is required. Please set GITHUB_BOT_NAME environment variable.")
    
    # Determine the correct email domain based on GitHub instance
    if api_url:
        # Extract domain from API URL
        parsed = urlparse(api_url)
        if parsed.netloc == "api.github.com":
            # GitHub.com
            email_domain = "users.noreply.github.com"
        else:
            # GitHub Enterprise - use the enterprise domain
            enterprise_domain = parsed.netloc
            if enterprise_domain.startswith("api."):
                # Remove 'api.' prefix if present
                enterprise_domain = enterprise_domain[4:]
            elif "/api/v3" in api_url:
                # Extract base domain from URL like https://github.enterprise.com/api/v3
                base_url = api_url.replace("/api/v3", "")
                enterprise_domain = urlparse(base_url).netloc
            email_domain = f"users.noreply.{enterprise_domain}"
    else:
        # Fallback to github.com if no API URL provided
        email_domain = "users.noreply.github.com"
    
    author_name = bot_name
    author_email = f"{bot_user_id}+{bot_name}@{email_domain}"
    
    return {
        "author_name": author_name,
        "author_email": author_email,
        "committer_name": author_name,
        "committer_email": author_email,
    }


def get_git_env(bot_user_id: Optional[str] = None, bot_name: Optional[str] = None, api_url: Optional[str] = None) -> Dict[str, str]:
    """
    Get git environment variables for non-interactive operation.
    
    Args:
        bot_user_id: Optional GitHub App bot user ID to set git author/committer information
        bot_name: Bot name (required when bot_user_id is provided, must be set via GITHUB_BOT_NAME env var)
        api_url: GitHub API URL to determine the correct email domain
    
    Returns:
        Dictionary of environment variables for git operations
    """
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",  # Disable terminal prompts
        "GIT_ASKPASS": "echo",       # Use echo as askpass (returns empty)
    }
    
    # If bot_user_id is provided, set git author/committer information
    if bot_user_id:
        author_info = get_codebot_git_author_info(bot_user_id, bot_name, api_url)
        env["GIT_AUTHOR_NAME"] = author_info["author_name"]
        env["GIT_AUTHOR_EMAIL"] = author_info["author_email"]
        env["GIT_COMMITTER_NAME"] = author_info["committer_name"]
        env["GIT_COMMITTER_EMAIL"] = author_info["committer_email"]
    
    return env


def generate_short_uuid() -> str:
    """Generate a short UUID (7 characters) for use in branch names and directory names."""
    uuid_str = str(uuid.uuid4())
    sha256_hash = hashlib.sha256(uuid_str.encode()).hexdigest()
    return sha256_hash[:7]


def generate_branch_name(
    ticket_id: Optional[str] = None,
    short_name: Optional[str] = None,
    uuid_part: Optional[str] = None,
) -> str:
    """
    Generate a branch name in the format: u/codebot/[TICKET-ID/]<uuid>/<short-name>
    
    Args:
        ticket_id: Optional ticket ID (e.g., "PROJ-123")
        short_name: Short descriptive name for the task
        uuid_part: Optional UUID to use (generates new one if not provided)
        
    Returns:
        Branch name string
    """
    if uuid_part is None:
        uuid_part = generate_short_uuid()
    
    parts = ["u", "codebot"]
    
    if ticket_id:
        parts.append(ticket_id)
    
    parts.append(uuid_part)
    
    if short_name:
        parts.append(short_name)
    
    return "/".join(parts)


def generate_directory_name(ticket_id: Optional[str] = None, uuid_part: Optional[str] = None) -> str:
    """
    Generate a directory name in the format: task_[TICKET-ID_]uuid
    
    Args:
        ticket_id: Optional ticket ID (e.g., "PROJ-123")
        uuid_part: Optional UUID to use (generates new one if not provided)
        
    Returns:
        Directory name string
    """
    if uuid_part is None:
        uuid_part = generate_short_uuid()
    
    if ticket_id:
        return f"task_{ticket_id}_{uuid_part}"
    else:
        return f"task_{uuid_part}"


def extract_uuid_from_branch(branch_name: str) -> Optional[str]:
    """
    Extract UUID from a codebot branch name.
    
    Branch format: u/codebot/[TICKET-ID/]UUID[/name]
    
    Args:
        branch_name: Branch name (e.g., "u/codebot/TASK-123/abc1234/feature")
        
    Returns:
        UUID string or None if not found
    """
    parts = branch_name.split("/")
    
    # Branch should start with u/codebot
    if len(parts) < 3 or parts[0] != "u" or parts[1] != "codebot":
        return None
    
    # Find the UUID part (7-character hash)
    for part in parts[2:]:
        if len(part) == 7 and all(c in "0123456789abcdef" for c in part):
            return part
    
    return None


def find_workspace_by_uuid(base_dir: Path, uuid: str) -> Optional[Path]:
    """
    Find a workspace directory by UUID.
    
    Workspace format: task_[TICKET-ID_]uuid
    
    Args:
        base_dir: Base directory containing workspaces
        uuid: UUID to search for
        
    Returns:
        Path to workspace or None if not found
    """
    if not base_dir.exists():
        return None
    
    # Search for directories matching the pattern
    for item in base_dir.iterdir():
        if item.is_dir() and item.name.endswith(f"_{uuid}"):
            return item
        elif item.is_dir() and item.name == f"task_{uuid}":
            return item
    
    return None


def cleanup_workspace(workspace_path: Path) -> bool:
    """
    Safely delete a workspace directory and all its contents.
    
    Args:
        workspace_path: Path to the workspace directory to delete
        
    Returns:
        True if deletion was successful, False otherwise
    """
    if not workspace_path.exists():
        return False
    
    if not workspace_path.is_dir():
        return False
    
    try:
        shutil.rmtree(workspace_path)
        return True
    except Exception as e:
        print(f"Warning: Failed to delete workspace {workspace_path}: {e}")
        return False


def cleanup_pr_workspace(
    branch_name: str,
    workspace_base_dir: Path,
    pr_number: Optional[int] = None,
    pr_url: Optional[str] = None,
    merged: Optional[bool] = None,
) -> tuple[bool, str]:
    """
    Central function to clean up workspace for a closed PR.
    
    This function:
    1. Extracts UUID from branch name
    2. Finds workspace by UUID
    3. Updates task status (completed/rejected) if merged parameter is provided
    4. Deletes workspace directory
    
    Args:
        branch_name: Branch name (e.g., "u/codebot/TASK-123/abc1234/feature")
        workspace_base_dir: Base directory containing workspaces
        pr_number: Optional PR number for logging
        pr_url: Optional PR URL for finding task
        merged: Optional boolean indicating if PR was merged (for task status update)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Only clean up workspaces for codebot branches
    if not branch_name.startswith("u/codebot/"):
        return False, "Not a codebot branch"
    
    # Extract UUID from branch name
    uuid = extract_uuid_from_branch(branch_name)
    if not uuid:
        return False, f"Could not extract UUID from branch: {branch_name}"
    
    # Find workspace by UUID
    workspace_path = find_workspace_by_uuid(workspace_base_dir, uuid)
    if not workspace_path:
        return False, f"No workspace found for UUID: {uuid}"
    
    # Find task and update status if merged parameter is provided
    task = global_task_store.find_task_by_branch_uuid(uuid)
    if not task and pr_url:
        task = global_task_store.find_task_by_pr_url(pr_url)
    
    # Update task status if merged parameter is provided
    if task and merged is not None:
        if merged:
            global_task_store.update_task(
                task.id,
                status="completed",
                completed_at=datetime.utcnow()
            )
        else:
            global_task_store.update_task(
                task.id,
                status="rejected",
                completed_at=datetime.utcnow()
            )
    
    # Clean up workspace
    if cleanup_workspace(workspace_path):
        pr_info = f"PR #{pr_number}" if pr_number else "PR"
        return True, f"Successfully cleaned up workspace for {pr_info}: {workspace_path}"
    else:
        return False, f"Failed to delete workspace: {workspace_path}"
