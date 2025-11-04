# Architecture

Learn how Codebot works internally and understand its components.

## Overview

Codebot is organized into four main packages:

```
codebot/
├── cli_runner/     # CLI task execution
├── server/         # Webhook and HTTP server
├── core/           # Shared core logic
└── claude/         # Claude Code integration
```

## Workflow

### CLI Task Execution

When you run `codebot run`:

1. **Parse Task Prompt** - Validates JSON/YAML configuration
2. **Setup Environment** - Creates isolated workspace, clones repository
3. **Check for CLAUDE.md** - Looks for project-specific guidance
4. **Run Claude Code CLI** - Executes AI agent with system prompt
5. **Verify Commits** - Ensures changes were committed
6. **Push Branch** - Pushes new branch to remote
7. **Create PR** - Creates pull request on GitHub
8. **Summary** - Displays results and PR URL

### HTTP API Task Execution

When a task is submitted via API:

1. **Receive Request** - Validates API key and request body
2. **Generate Task ID** - Creates unique UUID for tracking
3. **Enqueue Task** - Adds to FIFO task queue
4. **Return Task ID** - Responds immediately with 202 Accepted
5. **Worker Processes** - Background thread picks up task
6. **Execute with Orchestrator** - Same workflow as CLI
7. **Update Status** - Stores result (PR URL, branch name)
8. **Client Polls** - Status endpoint returns progress

### Webhook PR Review Handling

When a PR review comment is posted:

1. **Receive Webhook** - GitHub sends event to `/webhook`
2. **Verify Signature** - Validates HMAC signature
3. **Filter Comments** - Ignores codebot's own comments
4. **Enqueue Comment** - Adds to FIFO review queue
5. **Classify Intent** - Uses Claude to determine query vs change request
6. **Reuse Workspace** - Finds existing workspace by UUID
7. **Process with Claude** - Provides full context (PR, code, thread)
8. **Make Changes** (if needed) - Commits and pushes
9. **Update PR Description** - Refreshes with latest changes
10. **Post Reply** - Comments on GitHub thread

## Components

### Core Modules (`codebot/core/`)

**models.py**
- `TaskPrompt` - Task configuration dataclass
- `Task` - Task execution tracking

**parser.py**
- Parses JSON/YAML task prompts
- Validates required fields

**utils.py**
- UUID generation and extraction
- Branch/directory naming
- GitHub token validation
- Git environment configuration

**environment.py**
- Creates isolated workspaces
- Clones repositories
- Manages branches
- Workspace reuse for webhooks

**git_ops.py**
- Git commit operations
- Branch pushing
- Commit message retrieval

**github_pr.py**
- PR creation and updates
- Comment posting and replies
- PR details and file changes
- Comment thread retrieval

**orchestrator.py**
- Coordinates all components
- Executes complete workflow
- Error handling and cleanup

### Claude Integration (`codebot/claude/`)

**runner.py**
- Runs Claude Code CLI in headless mode
- Comprehensive system prompt
- Extracts responses from stream output

**md_detector.py**
- Detects CLAUDE.md or Agents.md files
- Provides warnings if missing

### Server Modules (`codebot/server/`)

**flask_app.py**
- Creates Flask application
- Registers webhooks and API blueprints
- Health check endpoint

**webhook.py**
- GitHub webhook handlers
- Signature verification
- Review queue management

**api.py**
- REST API endpoints
- Request validation
- Response formatting

**auth.py**
- API key authentication decorator
- Header validation

**config.py**
- Configuration management
- Environment variable loading

**task_queue.py**
- Thread-safe task queue
- Status tracking
- Task listing and filtering

**task_processor.py**
- Background worker threads
- Task execution with orchestrator
- Result capture and storage

**review_processor.py**
- Review comment processing
- Comment classification with Claude
- Workspace management
- PR description updates

**review_runner.py**
- Specialized Claude runner for reviews
- Contextual system prompts
- Query vs change request handling

**app.py**
- CLI `serve` command
- Server initialization
- Processor thread management

### CLI Runner (`codebot/cli_runner/`)

**runner.py**
- CLI `run` command
- Task prompt parsing
- Orchestrator coordination

## AI Agent Workflow

Claude Code CLI follows a senior engineer workflow:

1. **Read and understand** the task description
   - Analyze requirements and scope
   - Identify challenges and dependencies

2. **Come up with a plan**
   - Break down into logical steps
   - Consider impact on existing code

3. **Implement the plan**
   - Write clean, maintainable code
   - Follow project conventions

4. **Write tests**
   - Create comprehensive tests
   - Update existing tests if needed

5. **Run all tests**
   - Execute full test suite
   - Fix any regressions

6. **Commit changes**
   - Clear, descriptive commit messages
   - Reference task/ticket IDs

## Naming Conventions

### Branch Names

Format: `u/codebot/[TICKET-ID/]<uuid>/<short-name>`

Examples:
- `u/codebot/abc1234/add-dark-mode`
- `u/codebot/PROJ-123/def5678/fix-login-bug`

Components:
- `u/codebot` - Namespace prefix
- `TICKET-ID` - Optional ticket/issue ID
- `uuid` - 7-character hash for uniqueness
- `short-name` - From ticket_summary or generated from description

### Directory Names

Format: `task_[TICKET-ID_]<uuid>`

Examples:
- `task_abc1234`
- `task_PROJ-123_def5678`

## Queue Architecture

### Separate Queues

Codebot uses **two independent queues**:

1. **Task Queue** - For HTTP API submissions
   - Processed by `TaskProcessor` workers
   - Configurable worker count (`--workers`)
   - Independent scaling

2. **Review Queue** - For webhook comments
   - Processed by `ReviewProcessor`
   - Single-threaded (sequential processing)
   - Prevents conflicts in PR updates

### FIFO Processing

Both queues use First-In-First-Out ordering:
- Predictable processing order
- No race conditions
- Stable workspace state

## Data Flow

### CLI Task

```
User → CLI → Parser → Orchestrator → Environment → Claude → Git → GitHub → PR
```

### HTTP API Task

```
Client → API → TaskQueue → TaskProcessor → Orchestrator → ... → Result
         ↓                                                        ↑
      Task ID ←─────────────── Status Endpoint ←─────────────────┘
```

### Webhook Review

```
GitHub → Webhook → ReviewQueue → ReviewProcessor → Claude → Git → GitHub
         ↓                                                          ↑
      Verify ←──────────────────────────────────────────────────────┘
```

## Security

### Authentication

- **API Keys**: Bearer token or X-API-Key header
- **Webhook Secrets**: HMAC-SHA256 signature verification
- **GitHub Tokens**: PAT with appropriate scopes

### Isolation

- **Workspaces**: Separate directories per task
- **Git Credentials**: Temporary embedding, then removed
- **Environment**: Non-interactive Git operations

## Scalability

### Vertical Scaling

- Increase `--workers` for more parallel tasks
- More CPU cores = more workers
- More memory = larger queue sizes

### Current Limitations

- In-memory queues (not persistent)

### Future Enhancements

- Redis/PostgreSQL/SQLite for queue persistence
- Task management via web interface 

## Next Steps

- [Examples](examples.md) - See practical use cases
- [Configuration](configuration.md) - Customize settings
- [CLI Usage](cli-usage.md) - Run tasks from command line

---

[← Back to Documentation](index.md)
