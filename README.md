# Codebot

AI-powered development automation tool that executes tasks using Claude Code CLI. Automate code changes, create pull requests, and respond to PR reviews—all powered by AI.

## Features

- **CLI Task Execution** - Run development tasks from the command line with simple YAML/JSON prompts
- **HTTP REST API** - Submit tasks programmatically with async execution and status tracking
- **PR Review Automation** - Automatically respond to PR review comments with code changes or answers
- **Isolated Workspaces** - Each task runs in a separate environment for safety
- **Smart PR Management** - Auto-generates branches, commits, and pull requests
- **Intelligent Comment Handling** - Uses Claude AI to classify and respond to review comments

## Quick Start

```bash
# Install dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/yourusername/codebot.git
cd codebot && uv sync

# Activate virtual environment
source .venv/bin/activate

# Set GitHub token
export GITHUB_TOKEN="your_github_token"

# Run a task
codebot run --task-prompt '{
  "repository_url": "https://github.com/user/repo.git",
  "description": "Add README with installation instructions"
}'
```

That's it! Codebot will clone the repo, make changes with Claude Code CLI, and create a pull request.

## Documentation

📚 **[Full Documentation](docs/index.md)**

- [Installation Guide](docs/installation.md) - Setup and prerequisites
- [CLI Usage](docs/cli-usage.md) - Command-line task execution
- [HTTP API](docs/http-api.md) - REST API for programmatic access
- [Webhooks](docs/webhooks.md) - Automated PR review handling
- [Configuration](docs/configuration.md) - Environment variables and settings
- [Architecture](docs/architecture.md) - How codebot works internally
- [Examples](docs/examples.md) - Practical use cases and recipes

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- [Claude Code CLI](https://www.anthropic.com/claude/docs/claude-code)
- Git with authentication
- GitHub Personal Access Token

### Install

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install codebot
git clone https://github.com/yourusername/codebot.git
cd codebot
uv sync

# Activate virtual environment
source .venv/bin/activate

# Verify installation
codebot --help
```

**Note:** You need to activate the virtual environment each time you open a new terminal, or use `uv run codebot` as a shortcut.

See [Installation Guide](docs/installation.md) for detailed instructions and troubleshooting.

## Usage Examples

### CLI - Run a Task

```bash
# Using a YAML file
codebot run --task-prompt-file task.yaml

# Using inline JSON
codebot run --task-prompt '{"repository_url": "...", "description": "..."}'
```

### HTTP API - Submit Task

```bash
curl -X POST http://localhost:5000/api/tasks/submit \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"repository_url": "...", "description": "..."}'
```

### Webhook Server - PR Reviews

```bash
# Start server
export GITHUB_WEBHOOK_SECRET="your_secret"
codebot serve --port 5000

# Configure GitHub webhook at:
# Repository Settings → Webhooks → Add webhook
```

See [Examples](docs/examples.md) for more use cases.

## Development Setup

### For Contributors

```bash
# Clone repository
git clone https://github.com/yourusername/codebot.git
cd codebot

# Install dependencies
uv sync

# Run tests
uv run python tests/test_imports.py

# Start development server with auto-reload
uv run codebot serve --port 5000 --debug
```

### Project Structure

```
codebot/
├── codebot/
│   ├── cli_runner/      # CLI task execution
│   ├── server/          # Webhook and HTTP server
│   ├── core/            # Shared core logic
│   └── claude/          # Claude Code integration
├── docs/                # Documentation
├── tests/               # Test files
└── main.py              # Entry point
```

### Running from Source

```bash
# Run CLI
uv run codebot run --task-prompt-file task.yaml

# Start server
uv run codebot serve --port 5000
```

## Configuration

Codebot uses environment variables for configuration:

```bash
# Required
export GITHUB_TOKEN="your_github_token"

# For webhook server
export GITHUB_WEBHOOK_SECRET="your_webhook_secret"

# For HTTP API
export CODEBOT_API_KEYS="secret-key-1,secret-key-2"
```

Or create a `.env` file:

```
GITHUB_TOKEN=your_github_token
GITHUB_WEBHOOK_SECRET=your_webhook_secret
CODEBOT_API_KEYS=secret-key-1,secret-key-2
```

See [Configuration Guide](docs/configuration.md) for all options.

## How It Works

1. **Parse Task** - Validates task configuration
2. **Setup Environment** - Creates isolated workspace and clones repository
3. **Run Claude Code CLI** - AI agent makes changes following senior engineer workflow
4. **Commit & Push** - Commits changes and pushes to new branch
5. **Create PR** - Opens pull request on GitHub with detailed description

See [Architecture](docs/architecture.md) for technical details.

## Known Limitations

- **Repository Cloning**: Each task clones the repository into a fresh workspace, which may be slow for large repositories with extensive history
- **GitHub Identity**: Comments and PRs are created using your Personal Access Token, so they appear under your GitHub account rather than as a bot user. For production use, we should consider creating a GitHub App for proper bot identity 

## Contributing

Contributions are welcome! Here's how to get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

Please ensure:
- Code follows existing style
- Tests pass
- Documentation is updated
- Commit messages are clear

## License

MIT License - see LICENSE file for details.

## Links

- [Documentation](docs/index.md)
- [Installation Guide](docs/installation.md)
- [Examples](docs/examples.md)
- [GitHub Repository](https://github.com/yourusername/codebot)
- [Issue Tracker](https://github.com/yourusername/codebot/issues)

---

Made with ❤️ by [ajibigad](https://github.com/ajibigad) using [Cursor](https://cursor.com/home)
