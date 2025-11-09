# CLI Usage Guide

Learn how to use Codebot from the command line to automate development tasks.

## Overview

The `codebot run` command executes development tasks by:
1. Cloning a repository into an isolated workspace
2. Running Claude Code CLI to make changes
3. Creating a pull request with the changes

## Basic Command

```bash
codebot run --task-prompt-file task.yaml
```

Or with inline JSON:

```bash
codebot run --task-prompt '{"repository_url": "https://github.com/user/repo.git", "description": "Add feature"}'
```

## Task Prompt Format

Task prompts can be provided as YAML or JSON files, or as inline strings.

### Required Fields

- `repository_url` (string) - Git URL to clone
- `description` (string) - Task description for Claude Code CLI

### Optional Fields

- `ticket_id` (string) - External ticket/issue ID (e.g., "PROJ-123")
- `ticket_summary` (string) - Short name for the ticket (e.g., "fix-login-bug")
- `test_command` (string) - Override auto-detected test command
- `base_branch` (string) - Branch to checkout from (default: auto-detect main/master)

## YAML Format

Create a file `task.yaml`:

```yaml
repository_url: https://github.com/user/repo.git
ticket_id: PROJ-123
ticket_summary: fix-login-bug
description: |
  Fix the login authentication bug where users cannot log in 
  with special characters in passwords.
  Ensure all tests pass.
```

Run it:

```bash
codebot run --task-prompt-file task.yaml
```

## JSON Format

Create a file `task.json`:

```json
{
  "repository_url": "https://github.com/user/repo.git",
  "ticket_id": "PROJ-123",
  "ticket_summary": "fix-login-bug",
  "description": "Fix the login authentication bug where users cannot log in with special characters in passwords.\nEnsure all tests pass."
}
```

Run it:

```bash
codebot run --task-prompt-file task.json
```

## Inline Task Prompt

For quick tasks, use inline JSON:

```bash
codebot run --task-prompt '{
  "repository_url": "https://github.com/user/repo.git",
  "description": "Add dark mode support to the application"
}'
```

## Command Line Options

### --task-prompt

Task prompt as JSON or YAML string.

```bash
codebot run --task-prompt '{"repository_url": "...", "description": "..."}'
```

### --task-prompt-file

Path to task prompt file (JSON or YAML).

```bash
codebot run --task-prompt-file task.yaml
```

### --work-dir

Base directory for workspaces (default: `./codebot_workspace`).

```bash
codebot run --task-prompt-file task.yaml --work-dir /tmp/codebot
```

### GitHub App Configuration

GitHub App authentication is required via environment variables. See [Configuration Guide](../docs/configuration.md) for setup instructions.

Required environment variables:
- `GITHUB_APP_ID` - GitHub App ID
- `GITHUB_APP_PRIVATE_KEY_PATH` - Path to private key file
- `GITHUB_APP_INSTALLATION_ID` - Installation ID

### --verbose

Enable verbose output for debugging.

```bash
codebot run --task-prompt-file task.yaml --verbose
```

## How It Works

When you run a task, Codebot follows this workflow:

1. **Parse Task Prompt** - Validates the task configuration
2. **Setup Environment** - Creates isolated workspace and clones repository
3. **Check for CLAUDE.md** - Looks for project-specific guidance
4. **Run Claude Code CLI** - Executes AI agent with comprehensive system prompt
5. **Verify Commits** - Ensures changes were committed
6. **Push Branch** - Pushes the new branch to remote
7. **Create PR** - Creates a pull request on GitHub
8. **Summary** - Displays results and PR URL

## Branch Naming

Branches are automatically named using the format:

```
u/codebot/[TICKET-ID/]<uuid>/<short-name>
```

Examples:
- `u/codebot/abc1234/add-dark-mode`
- `u/codebot/PROJ-123/def5678/fix-login-bug`

Where:
- `uuid` - 7-character hash for uniqueness
- `TICKET-ID` - Optional ticket ID from task prompt
- `short-name` - Generated from ticket_summary or description

## Directory Naming

Work directories are named:

```
task_[TICKET-ID_]<uuid>
```

Examples:
- `task_abc1234`
- `task_PROJ-123_def5678`

## AI Agent Workflow

Claude Code CLI follows a senior engineer workflow:

1. **Read and understand** the task description
2. **Come up with a plan** - Break down into logical steps
3. **Implement the plan** - Write clean, maintainable code
4. **Write tests** - Create comprehensive tests
5. **Run all tests** - Verify no regressions
6. **Commit changes** - With clear, descriptive messages

## CLAUDE.md Support

If your repository has a `CLAUDE.md` or `Agents.md` file, Claude Code CLI will use it for:
- Test commands
- Environment setup instructions
- Code style guidelines
- Repository conventions

Example `CLAUDE.md`:

```markdown
# Project Guidelines

## Testing
Run tests with: `npm test`

## Code Style
- Use TypeScript strict mode
- Follow Airbnb style guide
- Add JSDoc comments for public APIs

## Conventions
- Feature branches: `feature/description`
- Commit format: `type(scope): message`
```

## Examples

See the [Examples Guide](examples.md) for more practical use cases.

## Troubleshooting

For CLI issues, task failures, and other problems, see the [Troubleshooting Guide](troubleshooting.md).

## Next Steps

- [HTTP API Guide](http-api.md) - Submit tasks programmatically
- [Configuration Guide](configuration.md) - Customize settings
- [Examples](examples.md) - See more use cases

---

[← Back to Documentation](index.md)

