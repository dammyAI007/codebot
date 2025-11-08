# Installation Guide

This guide will help you install and set up Codebot on your system.

## Prerequisites

Before installing Codebot, ensure you have the following:

### Required

- **Python 3.11+** - Codebot requires Python 3.11 or higher
- **uv package manager** - For dependency management
- **Claude Code CLI** - The AI agent that performs code changes
- **Git** - Configured with authentication for cloning repositories
- **GitHub App** - Registered GitHub App with private key and installation ID

### System Requirements

- macOS or Linux
- At least 2GB of free disk space
- Internet connection for API calls and repository access

## Step 1: Install uv Package Manager

If you don't have `uv` installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify installation:

```bash
uv --version
```

## Step 2: Install Claude Code CLI

Follow the official instructions at [Anthropic's Claude Code Documentation](https://www.anthropic.com/claude/docs/claude-code) to install Claude Code CLI.

Verify installation:

```bash
claude --version
```

## Step 3: Install Codebot

```bash
# Clone the repository
git clone https://github.com/yourusername/codebot.git
cd codebot

# Install dependencies
uv sync

# For corporate environments with restricted PyPI access:
# uv sync --index-url https://pypi.company.com/simple

# Activate the virtual environment
source .venv/bin/activate

# Verify installation
codebot --help
```

**Note:** You need to activate the virtual environment each time you open a new terminal, or use `uv run codebot` as a shortcut without activation.

## Step 4: Configure GitHub App

Codebot uses a GitHub App for authentication, allowing it to act with its own identity instead of a user's identity.

### Create a GitHub App

1. Go to your organization or user settings → Developer settings → GitHub Apps
2. Click "New GitHub App"
3. Fill in app details:
   - **Name**: codebot-007 (or your preferred name)
   - **Homepage URL**: Your app homepage
   - **Webhook URL**: Your webhook endpoint (if using webhook server)
4. Set required permissions:
   - **Contents**: Read and Write
   - **Pull requests**: Read and Write
   - **Metadata**: Read-only (automatic)
5. Click "Create GitHub App"

### Install the GitHub App

1. After creating the app, click "Install App"
2. Select the organization or repositories where you want to install it
3. Note the **Installation ID** from the URL (e.g., `https://github.com/settings/installations/123456`)

### Generate Private Key

1. In your GitHub App settings, scroll to "Private keys"
2. Click "Generate a private key"
3. Download the `.pem` file and store it securely (never commit to version control)

### Set Configuration

**Option 1: Environment Variables**

```bash
export GITHUB_APP_ID="123456"
export GITHUB_APP_PRIVATE_KEY_PATH="/path/to/private-key.pem"
export GITHUB_APP_INSTALLATION_ID="789012"
```

**Option 2: .env File**

Create a `.env` file in your project directory:

```bash
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=./codebot-private-key.pem
GITHUB_APP_INSTALLATION_ID=789012
```

See [Configuration Guide](configuration.md) for detailed GitHub App setup instructions.

## Step 5: Verify Installation

Test that everything is working:

```bash
# Check codebot command
uv run codebot --help

# Verify GitHub token
uv run codebot run --help
```

You should see the help output for the codebot CLI.

## Optional: Webhook Server Setup

If you plan to use the webhook server for PR review automation:

### 1. Set Webhook Secret

```bash
export GITHUB_WEBHOOK_SECRET="your_webhook_secret_here"
```

### 2. Set API Keys (for HTTP API)

```bash
export CODEBOT_API_KEYS="secret-key-1,secret-key-2"
```

### 3. Configure GitHub Webhook

See the [Webhooks Guide](webhooks.md) for detailed webhook configuration.

## Corporate Environment Setup

If you're in a corporate environment where PyPI access is restricted, you may need to use an internal PyPI mirror.

### Using Internal PyPI Mirror

```bash
# Install with custom index URL
uv sync --index-url https://pypi.company.com/simple

# Or set it permanently in .uv.toml
echo '[index]' > .uv.toml
echo 'url = "https://pypi.company.com/simple"' >> .uv.toml
```

### Managing uv.lock Changes

The `uv.lock` file may be updated when using different index URLs. This is normal and ensures reproducible builds in your environment. You have two options:

**Option 1: Commit the updated lock file** (recommended for teams using the same corporate environment)
```bash
git add uv.lock
git commit -m "Update uv.lock for corporate PyPI mirror"
```

**Option 2: Keep local changes only** (if working in mixed environments)
```bash
# Reset the lock file to avoid committing corporate-specific changes
git checkout HEAD -- uv.lock
```

### Environment-Specific Configuration

Create a `.uv.toml` file that can be customized per environment without affecting the repository:

```toml
# .uv.toml (add to .gitignore if needed)
[index]
url = "https://pypi.company.com/simple"
```

## Troubleshooting

For installation issues and common problems, see the [Troubleshooting Guide](troubleshooting.md).

## Next Steps

- [CLI Usage Guide](cli-usage.md) - Learn how to run tasks
- [Configuration Guide](configuration.md) - Customize codebot settings
- [Examples](examples.md) - See practical use cases

---

[← Back to Documentation](index.md)

