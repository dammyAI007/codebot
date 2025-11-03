# Codebot

CLI tool to work on tasks using AI agents like Claude Code CLI. Automate development tasks by cloning repositories, running Claude Code CLI in headless mode, and creating GitHub pull requests.

## Features

- **Automated Task Execution**: Accept task prompts in JSON or YAML format
- **Isolated Development Environments**: Create temporary directories for each task
- **Git Branch Management**: Automatically create branches with descriptive names
- **Claude Code Integration**: Run Claude Code CLI in headless mode to make changes
- **GitHub PR Creation**: Automatically create pull requests with task details
- **Flexible Configuration**: Support for custom test commands and base branches

## Installation

### Prerequisites

- Python 3.11+
- `uv` package manager
- Claude Code CLI installed (see [Claude Code Documentation](https://www.anthropic.com/claude/docs/claude-code))
- Git configured with authentication
- GitHub token for PR creation

### Install Dependencies

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install codebot
cd codebot
uv sync
```

### Install Claude Code CLI

Follow the instructions at [Anthropic's Claude Code Documentation](https://www.anthropic.com/claude/docs/claude-code) to install the Claude Code CLI.

## Usage

### Basic Usage

#### Running Tasks

```bash
# Using a task prompt file
codebot run --task-prompt-file task.yaml

# Using inline task prompt (JSON)
codebot run --task-prompt '{"repository_url": "https://github.com/user/repo.git", "description": "Fix bug"}'
```

#### Starting Webhook Server for PR Review Comments

```bash
# Start webhook server
codebot serve --port 5000

# With custom work directory
codebot serve --port 5000 --work-dir /path/to/workspaces

# Development mode with auto-reload
codebot serve --port 5000 --debug
```

### Task Prompt Format

The task prompt should be in JSON or YAML format with the following fields:

- `repository_url` (required): Git URL to clone
- `description` (required): The actual task prompt for Claude Code CLI
- `ticket_id` (optional): External ticket/issue ID
- `ticket_summary` (optional): Short name for the ticket
- `test_command` (optional): Override auto-detected test command
- `base_branch` (optional): Branch to checkout from (default: auto-detect)

#### Example YAML:

```yaml
repository_url: https://github.com/user/repo.git
ticket_id: PROJ-123
ticket_summary: fix-login-bug
description: |
  Fix the login authentication bug where users cannot log in with special characters in passwords.
  Ensure all tests pass.
```

#### Example JSON:

```json
{
  "repository_url": "https://github.com/user/repo.git",
  "ticket_id": "PROJ-123",
  "ticket_summary": "fix-login-bug",
  "description": "Fix the login authentication bug where users cannot log in with special characters in passwords.\nEnsure all tests pass."
}
```

### Command Line Options

```
Options:
  --task-prompt TEXT       Task prompt as JSON or YAML string
  --task-prompt-file PATH  Path to task prompt file (JSON or YAML)
  --work-dir PATH          Base directory for work spaces (defaults to ./codebot_workspace)
  --github-token TEXT      GitHub token (defaults to GITHUB_TOKEN env var or .env file)
  --verbose                Enable verbose output
  --help                   Show this message and exit
```

### Environment Variables

- `GITHUB_TOKEN`: GitHub personal access token for creating pull requests
- `GITHUB_WEBHOOK_SECRET`: Secret for verifying GitHub webhook signatures (required for `serve` command)

You can also create a `.env` file in your project directory with:
```
GITHUB_TOKEN=your_github_token_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
```

**GitHub Token Requirements:**
- For private repositories: Token needs `repo` scope (classic tokens) or `Contents: Read/Write` and `Pull requests: Write` (fine-grained tokens)
- For public repositories: Token needs `public_repo` scope or `Contents: Write` and `Pull requests: Write`
- Token is validated before use to prevent authentication failures
- Credentials are only embedded temporarily during clone, then removed for security

## How It Works

1. **Parse Task Prompt**: Reads and validates the task prompt
2. **Setup Environment**: Creates an isolated directory and clones the repository
3. **Check for CLAUDE.md**: Looks for CLAUDE.md or Agents.md in the repository
4. **Run Claude Code CLI**: Executes Claude Code CLI in headless mode with a comprehensive system prompt that guides the AI through a senior engineer workflow
5. **Verify Commits**: Ensures changes are committed
6. **Push Branch**: Pushes the branch to the remote repository
7. **Create PR**: Creates a pull request on GitHub with the task details

## Branch Naming

Branches are automatically named using the format:
```
u/codebot/[TICKET-ID/]<uuid>/<short-name>
```

Where:
- `uuid` is a 7-character hash generated from a UUID4
- `TICKET-ID` is optional and comes from the task prompt
- `short-name` is from `ticket_summary` or generated from the description

## Directory Naming

Work directories are named using the format:
```
task_[TICKET-ID_]<uuid>
```

Where:
- `uuid` is a 7-character hash
- `TICKET-ID` is included only if provided in the task prompt

## AI Agent Workflow

Codebot uses a comprehensive system prompt that guides the AI agent through a senior engineer workflow:

1. **Read and understand the task description** - Carefully analyze requirements and scope
2. **Come up with a plan** - Break down the task into logical steps and consider impact
3. **Implement your plan** - Write clean, maintainable code following best practices
4. **Write tests and run them** - Create comprehensive tests and verify changes work
5. **Run all tests** - Execute the full test suite to ensure no regressions
6. **Commit changes** - Create clear, descriptive commit messages highlighting changes

The AI agent follows important guidelines including:
- Prioritizing code quality and maintainability
- Following project patterns and conventions
- Considering edge cases and error handling
- Documenting complex logic with clear comments
- Ensuring backward compatibility when possible
- Completing tasks fully before finishing

## CLAUDE.md Support

Codebot supports repositories with `CLAUDE.md` or `Agents.md` files. These files should contain:
- Test commands
- Environment setup instructions
- Code style guidelines
- Repository conventions

Claude Code CLI automatically uses these files for context when making changes.

## PR Review Comment Handling

Codebot can automatically respond to review comments on pull requests it creates. This feature requires running a webhook server that listens for GitHub events.

### Setup Webhook Server

1. **Start the webhook server:**
   ```bash
   codebot serve --port 5000
   ```

2. **Configure GitHub webhook:**
   - Go to your repository Settings > Webhooks
   - Click "Add webhook"
   - Set Payload URL: `https://your-server.com/webhook` (use a service like ngrok for local testing)
   - Set Content type: `application/json`
   - Set Secret: Same value as your `GITHUB_WEBHOOK_SECRET` environment variable
   - Select individual events:
     - ✅ Issue comments (for general PR comments)
     - ✅ Pull request reviews (for review summaries)
     - ✅ Pull request review comments (for inline code comments)
   - Click "Add webhook"

3. **Verify webhook is working:**
   - Check the health endpoint: `http://localhost:5000/health`
   - Create a review comment on a codebot PR to test

### How Review Comments Work

Codebot handles three types of PR comments:

1. **General PR comments** (issue_comment event) - Comments on the PR conversation
2. **Inline code comments** (pull_request_review_comment event) - Comments on specific lines
3. **Review summaries** (pull_request_review event) - Overall review with approval/changes requested

When a reviewer leaves any of these comments on a codebot-created PR:

1. **Comment Classification**: Claude AI analyzes the comment with full context to determine intent
2. **Workspace Reuse**: Codebot finds and reuses the existing workspace for that PR branch, or clones fresh if needed
3. **Claude Code Processing**: 
   - For **queries**: Claude provides a concise, direct answer without making code changes
   - For **change requests**: Claude makes the requested changes, tests them, commits, and updates the PR description
   - For **ambiguous**: Codebot asks the reviewer to clarify their intent
4. **Response**: Codebot posts a reply to the comment thread with:
   - For queries: A concise but sufficient answer
   - For changes: A brief summary of changes made and test results
   - For ambiguous: A question asking for clarification
5. **Recursion Prevention**: Codebot ignores its own comments to avoid infinite loops

### Comment Classification

Codebot uses Claude AI to intelligently classify comments into three categories:

1. **Query/Question** - The reviewer is asking for clarification or information
   - Example: "Why did you choose this approach?", "What does this parameter do?"
   - Response: Claude provides a concise, direct answer without making code changes

2. **Change Request** - The reviewer is requesting specific code modifications
   - Example: "Please add error handling", "This should use async/await"
   - Response: Claude makes the changes, tests them, commits, and updates the PR description

3. **Ambiguous** - The intent is unclear and needs clarification
   - Example: "This could be better", "Not sure about this"
   - Response: Codebot asks the reviewer to clarify if they want an answer or code changes

This AI-powered classification is more accurate than keyword matching and understands context from:
- The PR title and description
- Files changed in the PR
- The specific code being reviewed (file, line, diff hunk)
- Previous comments in the thread

### FIFO Queue Processing

Multiple review comments are processed one at a time in FIFO (First-In-First-Out) order to ensure:
- No conflicts between concurrent changes
- Predictable processing order
- Stable workspace state

### PR Description Updates

After Claude makes changes in response to review comments, codebot automatically updates the PR description to reflect all changes:
- Uses Claude AI to analyze the full diff between the PR branch and main
- Generates a unified, cohesive description of all changes
- Focuses on what was built and how it works, not individual commits
- Simplifies the "Files Changed" section:
  - Shows only file names (not diff stats)
  - Omits the section entirely if more than 5 files changed (GitHub already shows this)

This ensures reviewers always see an up-to-date summary of the PR's complete functionality.

### Development Mode

When developing codebot itself, use `--debug` flag for a better experience:

```bash
codebot serve --port 5000 --debug
```

**Debug mode features:**
- **Auto-reload**: Server automatically restarts when you edit Python files
- **Detailed errors**: Shows full stack traces in the browser
- **Better logging**: More verbose output for debugging

**Note**: Never use `--debug` in production - it's slower and exposes error details.

## HTTP API

Codebot provides HTTP REST API endpoints for programmatic task submission with async execution and status tracking.

### Setup

1. **Set API Keys** (comma-separated for multiple keys):
```bash
export CODEBOT_API_KEYS="your-secret-key-1,your-secret-key-2"
```

2. **Start Server with API Enabled**:
```bash
codebot serve --port 5000 --workers 2
```

The `--workers` flag controls how many tasks can be processed in parallel.

### API Endpoints

#### Submit a Task

**POST** `/api/tasks/submit`

Submit a new task for async execution.

**Authentication**: Required (API key in `Authorization: Bearer <key>` or `X-API-Key: <key>` header)

**Request Body**:
```json
{
  "repository_url": "https://github.com/user/repo.git",
  "description": "Add dark mode support to the application",
  "ticket_id": "FEAT-123",
  "ticket_summary": "add-dark-mode",
  "test_command": "npm test",
  "base_branch": "main"
}
```

**Required fields**: `repository_url`, `description`

**Response** (202 Accepted):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Task queued successfully"
}
```

**Example**:
```bash
curl -X POST http://localhost:5000/api/tasks/submit \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "repository_url": "https://github.com/user/repo.git",
    "description": "Add dark mode support"
  }'
```

#### Get Task Status

**GET** `/api/tasks/{task_id}/status`

Check the status and results of a task.

**Authentication**: Required

**Response** (200 OK):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "submitted_at": "2025-11-03T12:00:00Z",
  "started_at": "2025-11-03T12:00:05Z",
  "completed_at": "2025-11-03T12:05:30Z",
  "result": {
    "pr_url": "https://github.com/user/repo/pull/123",
    "branch_name": "u/codebot/abc1234/add-dark-mode",
    "work_dir": "/path/to/workspace"
  }
}
```

**Status values**: `pending`, `running`, `completed`, `failed`

**Example**:
```bash
curl http://localhost:5000/api/tasks/550e8400-e29b-41d4-a716-446655440000/status \
  -H "Authorization: Bearer your-api-key"
```

#### List Tasks

**GET** `/api/tasks?status=completed&limit=50`

List recent tasks with optional filtering.

**Authentication**: Required

**Query Parameters**:
- `status` (optional): Filter by status (`pending`, `running`, `completed`, `failed`)
- `limit` (optional): Max results (1-1000, default: 100)

**Response** (200 OK):
```json
{
  "tasks": [
    {
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "submitted_at": "2025-11-03T12:00:00Z",
      "started_at": "2025-11-03T12:00:05Z",
      "completed_at": "2025-11-03T12:05:30Z",
      "repository_url": "https://github.com/user/repo.git",
      "description": "Add dark mode support to the application"
    }
  ],
  "count": 1
}
```

**Example**:
```bash
curl "http://localhost:5000/api/tasks?status=completed&limit=10" \
  -H "Authorization: Bearer your-api-key"
```

### API Features

- **Async Execution**: Tasks are queued and processed in the background
- **Status Tracking**: Monitor task progress via status endpoint
- **Scalable Workers**: Configure multiple worker threads with `--workers`
- **Separate Queues**: API tasks and webhook review comments use independent queues
- **Secure**: API key authentication required
- **FIFO Processing**: Tasks are processed in order of submission

### Configuration

Environment variables for API:
- `CODEBOT_API_KEYS`: Comma-separated list of valid API keys
- `CODEBOT_MAX_WORKERS`: Maximum worker threads (default: 1)
- `CODEBOT_MAX_QUEUE_SIZE`: Maximum tasks in queue (default: 100)
- `CODEBOT_TASK_RETENTION`: Task data retention in seconds (default: 86400)

## Examples

### Simple Bug Fix

```yaml
# bug-fix.yaml
repository_url: https://github.com/user/myproject.git
description: Fix the null pointer exception in UserService.java
```

```bash
codebot --task-prompt-file bug-fix.yaml
```

### Feature with Ticket ID

```yaml
# feature.yaml
repository_url: https://github.com/user/myproject.git
ticket_id: FEA-456
ticket_summary: add-dark-mode
description: |
  Add dark mode support to the application.
  Include a toggle in the settings page.
  Ensure all existing tests still pass.
```

```bash
codebot --task-prompt-file feature.yaml
```

### Custom Base Branch

```yaml
# custom-branch.yaml
repository_url: https://github.com/user/myproject.git
base_branch: develop
description: Backport security fix to develop branch
```

```bash
codebot --task-prompt-file custom-branch.yaml
```

## Future Enhancements

- Docker/dev container support for even more isolated environments
- GitHub MCP integration for AI agent capabilities
- Support for multiple repository cloning
- Automated cleanup of temporary directories

## License

MIT
