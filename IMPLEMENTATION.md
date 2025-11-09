# Codebot Implementation Summary

This document summarizes the implementation of the Codebot CLI tool.

## Overview

Codebot is a CLI tool that automates AI-assisted development tasks by:
1. Accepting task prompts in JSON or YAML format
2. Cloning repositories into isolated environments
3. Running Claude Code CLI in headless mode to make changes
4. Committing changes and creating GitHub pull requests

## Architecture

Codebot is organized into four main packages:

### 1. `codebot/cli_runner/` - CLI Task Execution
- `runner.py`: Implements the `run` command for executing tasks from the CLI
- Handles task prompt parsing and validation
- Manages GitHub token validation
- Coordinates with the orchestrator to execute tasks

### 2. `codebot/server/` - Webhook and HTTP Server
- `app.py`: Implements the `serve` command for starting the webhook server
- `webhook_server.py`: Flask-based webhook endpoint for GitHub events
- `review_processor.py`: Processes PR review comments from the queue
- `review_runner.py`: Specialized Claude runner for review comments

### 3. `codebot/core/` - Shared Core Logic
- `models.py`: Data models (TaskPrompt)
- `parser.py`: Task prompt parsing (JSON/YAML)
- `utils.py`: Utility functions (UUID generation, branch naming, validation)
- `environment.py`: Environment manager for isolated workspaces
- `git_ops.py`: Git operations (commit, push, branch management)
- `github_pr.py`: GitHub API integration (PR creation, comments)
- `orchestrator.py`: Main orchestrator coordinating all components

### 4. `codebot/claude/` - Claude Code Integration
- `runner.py`: Claude Code CLI integration and execution
- `md_detector.py`: CLAUDE.md file detection

### 5. `codebot/cli.py` - Thin Entry Point
- Main CLI entry point that delegates to `cli_runner` and `server` modules
- Registers the `run` and `serve` commands
- Loads environment variables

## Components Implemented

### Core Modules (codebot/core/)

#### 1. `models.py` - Data Models
- `TaskPrompt` dataclass with fields:
  - `repository_url` (required)
  - `description` (required)
  - `ticket_id` (optional)
  - `ticket_summary` (optional)
  - `test_command` (optional)
  - `base_branch` (optional)
- Includes validation for required fields

#### 2. `parser.py` - Task Prompt Parsing
- Supports both JSON and YAML formats
- Auto-detects format based on content
- `parse_task_prompt()` for string content
- `parse_task_prompt_file()` for file-based parsing

#### 3. `utils.py` - Utility Functions
- `generate_short_uuid()`: Creates 7-character UUID hash
- `generate_branch_name()`: Creates branch names in format `u/codebot/[TICKET-ID/]uuid/short-name`
- `generate_directory_name()`: Creates directory names in format `task_[TICKET-ID_]uuid`
- `validate_github_app_config()`: Validates GitHub App configuration
- `get_git_env()`: Returns non-interactive Git environment
- `extract_uuid_from_branch()`: Extracts UUID from branch names
- `find_workspace_by_uuid()`: Finds workspace directories by UUID

#### 4. `environment.py` - Environment Manager
- Creates isolated development environments
- Clones repositories into temporary directories
- Detects default branch (main/master)
- Creates and checks out new branches
- Manages git operations for environment setup
- Supports workspace reuse for PR review comments

#### 5. `git_ops.py` - Git Operations
- Commits changes with messages
- Pushes branches to remote
- Checks for uncommitted changes
- Retrieves commit hashes and branch names
- Gets commit messages

#### 6. `github_pr.py` - GitHub PR Creation and Management
- Extracts repo owner/name from URLs
- Creates pull requests via GitHub REST API
- Generates PR titles and bodies
- Uses GitHub token for authentication
- Supports both HTTPS and SSH URLs
- Posts PR comments and review comment replies
- Fetches PR details and files changed
- Updates PR descriptions
- Gets comment threads

#### 7. `orchestrator.py` - Main Orchestrator
- Coordinates all components in sequence:
  1. Parse task prompt
  2. Setup environment
  3. Check for CLAUDE.md
  4. Run Claude Code CLI
  5. Verify commits
  6. Push branch
  7. Create GitHub PR
  8. Summary output
- Handles errors gracefully
- Preserves work directories for inspection
- Tracks git state before and after Claude runs

### Claude Modules (codebot/claude/)

#### 1. `md_detector.py` - CLAUDE.md Detection
- Detects `CLAUDE.md` or `Agents.md` files
- Provides warnings if files are missing
- Supports project-specific guidance for Claude Code

#### 2. `runner.py` - Claude Code CLI Integration
- Checks if Claude Code CLI is installed
- Runs Claude Code in headless mode using `-p` flag
- Uses comprehensive system prompt that guides AI through engineering workflow
- Uses `--append-system-prompt` for additional instructions
- Uses `--output-format stream-json` for structured output
- Extracts Claude's final response from stream output
- Verifies changes were committed
- Retrieves commit messages

### Server Modules (codebot/server/)

#### 1. `app.py` - Webhook Server Command
- Implements the `serve` CLI command
- Validates GitHub token and webhook secret
- Starts Flask server and review processor
- Manages server lifecycle

#### 2. `webhook_server.py` - Flask Webhook Server
- Receives GitHub webhook events
- Verifies webhook signatures
- Handles three types of PR comments:
  - Issue comments (general PR comments)
  - Pull request reviews (review summaries)
  - Pull request review comments (inline code comments)
- Queues comments for processing (FIFO)
- Filters out codebot's own comments
- Health check endpoint

#### 3. `review_processor.py` - Review Comment Processor
- Processes review comments from queue sequentially
- Manages workspace reuse and updates
- Classifies comments using Claude AI (query/change request/ambiguous)
- Provides full context to Claude (PR details, code snippets, threads)
- Posts replies to GitHub
- Updates PR descriptions after changes
- Handles errors gracefully

#### 4. `review_runner.py` - Review-Specific Claude Runner
- Specialized Claude runner for PR review comments
- Builds contextual system prompts with:
  - PR title and description
  - Files changed
  - Comment location (file, line, diff hunk)
  - Full comment thread
- Handles both queries and change requests
- Extracts Claude's responses

### CLI Runner Module (codebot/cli_runner/)

#### 1. `runner.py` - Run Command Implementation
- Implements the `run` CLI command
- Parses task prompts from files or strings
- Validates GitHub tokens
- Creates and manages work directories
- Coordinates with orchestrator to execute tasks

### Supporting Files

- `pyproject.toml`: Package configuration with dependencies
- `README.md`: Comprehensive documentation and usage examples
- `example-task.yaml`: Example task prompt file
- `.gitignore`: Ignores virtual env and work directories

## Features Implemented

### Task Prompt Format
- Supports both JSON and YAML
- Required fields: `repository_url`, `description`
- Optional fields: `ticket_id`, `ticket_summary`, `test_command`, `base_branch`
- Automatic format detection

### Branch Naming
- Format: `u/codebot/[TICKET-ID/]<uuid>/<short-name>`
- UUID is a 7-character hash
- Includes ticket ID if provided
- Includes short name if provided

### Directory Naming
- Format: `task_[TICKET-ID_]uuid`
- Simpler format than branch names
- Excludes "u/codebot" prefix

### Claude Code Integration
- Headless mode execution
- Comprehensive system prompt with workflow guidance
- Six-step workflow: understand task → plan → implement → test → verify → commit
- Detailed guidelines for code quality, maintainability, and best practices
- Supports `CLAUDE.md` for project context
- Structured JSON output
- Error handling and logging

### Git Operations
- Automatic branch creation
- Commit verification
- Push to remote
- Supports existing git credentials

### GitHub PR Creation
- Automatic PR creation
- Title and body generation
- Ticket ID inclusion
- Task description in PR body
- GitHub API integration

### Error Handling
- Graceful error messages
- Work directory preservation on failure
- Verbose mode for debugging
- Clear progress indicators

## Dependencies

- `click`: CLI framework
- `pyyaml`: YAML parsing
- `requests`: GitHub API calls
- `python-dotenv`: Environment variable loading from .env files
- Standard library: `subprocess`, `pathlib`, `json`, `hashlib`, `uuid`, `dataclasses`

## Configuration

### Environment Variables
- `GITHUB_APP_ID`: GitHub App ID (can be set via environment variable or .env file)
- `GITHUB_APP_PRIVATE_KEY_PATH`: Path to GitHub App private key file
- `GITHUB_APP_INSTALLATION_ID`: GitHub App installation ID

### Command-Line Options
- `--task-prompt`: Inline task prompt (JSON/YAML)
- `--task-prompt-file`: File path to task prompt
- `--work-dir`: Base directory for work spaces
- `--verbose`: Enable verbose output

## Testing

- Import test verifies all modules can be imported
- CLI help test verifies command-line interface works
- All Python files compile successfully

## Future Enhancements

As noted in the README:
- Docker/dev container support
- GitHub MCP integration
- Multiple repository support
- Automated cleanup of temporary directories

## Usage Example

```bash
# Create a task file
cat > task.yaml << EOF
repository_url: https://github.com/user/repo.git
ticket_id: TASK-123
ticket_summary: fix-bug
description: |
  Fix the critical bug in the authentication system.
  Ensure all tests pass.
EOF

# Run codebot
codebot --task-prompt-file task.yaml
```

## Design Decisions

1. **Temporary Directory Persistence**: Work directories are left behind for inspection after task completion or failure

2. **UUID Generation**: Uses SHA256 hash of UUID4 for deterministic, collision-resistant 7-character IDs

3. **GitHub Token Handling**: Falls back to environment variable if not provided via command line

4. **Claude Code CLI Dependency**: Exits gracefully if Claude Code CLI is not installed with helpful error message

5. **Error Recovery**: Work directories are preserved to allow manual inspection and recovery

6. **CLAUDE.md Support**: Warns if not found but continues execution, as Claude Code can still work without it
