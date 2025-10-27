# Codebot Implementation Summary

This document summarizes the implementation of the Codebot CLI tool.

## Overview

Codebot is a CLI tool that automates AI-assisted development tasks by:
1. Accepting task prompts in JSON or YAML format
2. Cloning repositories into isolated environments
3. Running Claude Code CLI in headless mode to make changes
4. Committing changes and creating GitHub pull requests

## Components Implemented

### Core Modules

#### 1. `cli.py` - CLI Interface
- Uses Click framework for command-line parsing
- Accepts `--task-prompt` and `--task-prompt-file` options
- Supports `--work-dir`, `--github-token`, and `--verbose` flags
- Entry point for the application

#### 2. `models.py` - Data Models
- `TaskPrompt` dataclass with fields:
  - `repository_url` (required)
  - `description` (required)
  - `ticket_id` (optional)
  - `ticket_summary` (optional)
  - `test_command` (optional)
  - `base_branch` (optional)
- Includes validation for required fields

#### 3. `parser.py` - Task Prompt Parsing
- Supports both JSON and YAML formats
- Auto-detects format based on content
- `parse_task_prompt()` for string content
- `parse_task_prompt_file()` for file-based parsing

#### 4. `utils.py` - Utility Functions
- `generate_short_uuid()`: Creates 7-character UUID hash
- `generate_branch_name()`: Creates branch names in format `u/codebot/[TICKET-ID/]uuid/short-name`
- `generate_directory_name()`: Creates directory names in format `task_[TICKET-ID_]uuid`

#### 5. `environment.py` - Environment Manager
- Creates isolated development environments
- Clones repositories into temporary directories
- Detects default branch (main/master)
- Creates and checks out new branches
- Manages git operations for environment setup

#### 6. `claude_md_detector.py` - CLAUDE.md Detection
- Detects `CLAUDE.md` or `Agents.md` files
- Provides warnings if files are missing
- Supports project-specific guidance for Claude Code

#### 7. `claude_runner.py` - Claude Code CLI Integration
- Checks if Claude Code CLI is installed
- Runs Claude Code in headless mode using `-p` flag
- Uses comprehensive system prompt that guides AI through engineering workflow
- Uses `--append-system-prompt` for additional instructions
- Uses `--output-format stream-json` for structured output
- Verifies changes were committed
- Retrieves commit messages

#### 8. `git_ops.py` - Git Operations
- Commits changes with messages
- Pushes branches to remote
- Checks for uncommitted changes
- Retrieves commit hashes and branch names

#### 9. `github_pr.py` - GitHub PR Creation
- Extracts repo owner/name from URLs
- Creates pull requests via GitHub REST API
- Generates PR titles and bodies
- Uses GitHub token for authentication
- Supports both HTTPS and SSH URLs

#### 10. `orchestrator.py` - Main Orchestrator
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
- `GITHUB_TOKEN`: GitHub personal access token (can be set via environment variable or .env file)

### Command-Line Options
- `--task-prompt`: Inline task prompt (JSON/YAML)
- `--task-prompt-file`: File path to task prompt
- `--work-dir`: Base directory for work spaces
- `--github-token`: GitHub token override
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
