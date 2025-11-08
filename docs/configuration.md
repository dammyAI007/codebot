# Configuration Guide

Configure Codebot using environment variables and command-line options.

## Environment Variables

### Core Configuration

#### GITHUB_APP_ID

**Required**: Yes  
**Description**: GitHub App ID (numeric)  
**Example**: `123456`

```bash
export GITHUB_APP_ID="123456"
```

Or in `.env` file:

```
GITHUB_APP_ID=123456
```

#### GITHUB_APP_PRIVATE_KEY_PATH

**Required**: Yes  
**Description**: Path to GitHub App private key file (.pem)  
**Example**: `/path/to/private-key.pem` or `./codebot-private-key.pem`

```bash
export GITHUB_APP_PRIVATE_KEY_PATH="/path/to/private-key.pem"
```

Or in `.env` file:

```
GITHUB_APP_PRIVATE_KEY_PATH=./codebot-private-key.pem
```

**Note**: The private key file must be readable by the codebot process. Keep it secure and never commit it to version control.

#### GITHUB_APP_INSTALLATION_ID

**Required**: Yes  
**Description**: GitHub App Installation ID (numeric)  
**Example**: `789012`

```bash
export GITHUB_APP_INSTALLATION_ID="789012"
```

Or in `.env` file:

```
GITHUB_APP_INSTALLATION_ID=789012
```

**Note**: This is the installation ID for your GitHub App. You can find it in your GitHub App settings or via the API.

#### GITHUB_WEBHOOK_SECRET

**Required**: For webhook server  
**Description**: Secret for verifying GitHub webhook signatures  
**Example**: Any secure random string

```bash
export GITHUB_WEBHOOK_SECRET="your_webhook_secret_here"
```

### HTTP API Configuration

#### CODEBOT_API_KEYS

**Required**: For HTTP API  
**Description**: Comma-separated list of valid API keys  
**Example**: `secret-key-1,secret-key-2`

```bash
export CODEBOT_API_KEYS="secret-key-1,secret-key-2"
```

#### CODEBOT_MAX_WORKERS

**Default**: 1  
**Description**: Maximum number of task processor worker threads  
**Range**: 1-10 (recommended)

```bash
export CODEBOT_MAX_WORKERS=4
```

#### CODEBOT_MAX_QUEUE_SIZE

**Default**: 100  
**Description**: Maximum number of tasks in queue  
**Range**: 1-1000

```bash
export CODEBOT_MAX_QUEUE_SIZE=200
```

#### CODEBOT_TASK_RETENTION

**Default**: 86400 (24 hours)  
**Description**: Task data retention period in seconds  

```bash
export CODEBOT_TASK_RETENTION=172800  # 48 hours
```

## .env File Support

Create a `.env` file in your project directory:

```bash
# GitHub App Configuration
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=./codebot-private-key.pem
GITHUB_APP_INSTALLATION_ID=789012

# GitHub Webhook Configuration
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here

# GitHub Enterprise Configuration (if using enterprise)
GITHUB_ENTERPRISE_URL=https://github.company.com
GITHUB_API_URL=https://github.company.com/api/v3

# HTTP API Configuration
CODEBOT_API_KEYS=secret-key-1,secret-key-2
CODEBOT_MAX_WORKERS=2
CODEBOT_MAX_QUEUE_SIZE=100
CODEBOT_TASK_RETENTION=86400
```

Codebot automatically loads `.env` files on startup.

## Command-Line Options

### codebot run

```bash
codebot run [OPTIONS]
```

**Options:**

- `--task-prompt TEXT` - Task prompt as JSON or YAML string
- `--task-prompt-file PATH` - Path to task prompt file
- `--work-dir PATH` - Base directory for workspaces (default: `./codebot_workspace`)
- `--verbose` - Enable verbose output

### codebot serve

```bash
codebot serve [OPTIONS]
```

**Options:**

- `--port INTEGER` - Server port (default: 5000)
- `--work-dir PATH` - Base directory for workspaces
- `--webhook-secret TEXT` - Webhook secret (overrides env var)
- `--api-key TEXT` - API key (overrides env var)
- `--workers INTEGER` - Number of worker threads (default: 1)
- `--debug` - Enable debug mode with auto-reload

## GitHub App Setup

### Creating a GitHub App

1. Go to your organization or user settings → Developer settings → GitHub Apps
2. Click "New GitHub App"
3. Fill in app details:
   - **Name**: codebot-007 (or your preferred name)
   - **Homepage URL**: Your app homepage
   - **Webhook URL**: Your webhook endpoint (for webhook server)
   - **Webhook secret**: Set `GITHUB_WEBHOOK_SECRET` environment variable
4. Set required permissions:
   - **Repository permissions**:
     - Contents: Read and Write
     - Pull requests: Read and Write
     - Metadata: Read-only
5. Subscribe to webhook events (for webhook server):
   - Pull request review comments
   - Pull request reviews
   - Issue comments
6. Click "Create GitHub App"

### Installing the GitHub App

1. After creating the app, go to the app settings
2. Click "Install App"
3. Select the organization or repositories where you want to install it
4. Note the **Installation ID** from the URL or API response
5. Set `GITHUB_APP_INSTALLATION_ID` environment variable

### Generating Private Key

1. In your GitHub App settings, scroll to "Private keys"
2. Click "Generate a private key"
3. Download the `.pem` file
4. Store it securely (never commit to version control)
5. Set `GITHUB_APP_PRIVATE_KEY_PATH` environment variable to the file path

### Required Permissions

The GitHub App needs the following permissions:
- **Contents**: Read and Write (for cloning, pushing, and reading files)
- **Pull requests**: Read and Write (for creating PRs and commenting)
- **Metadata**: Read-only (automatic, for repository access)

## Workspace Configuration

### Work Directory Structure

```
codebot_workspace/
├── task_abc1234/          # Task workspace
│   └── repo/              # Cloned repository
├── task_PROJ-123_def5678/ # Task with ticket ID
│   └── repo/
└── ...
```

### Custom Work Directory

```bash
# CLI
codebot run --work-dir /tmp/codebot_tasks --task-prompt-file task.yaml

# Server
codebot serve --work-dir /var/codebot/workspaces
```

## Server Configuration

### Production Recommendations

```bash
# Use production WSGI server (not Flask dev server)
export CODEBOT_MAX_WORKERS=4
export CODEBOT_MAX_QUEUE_SIZE=200

# Don't use --debug in production
codebot serve --port 8000 --workers 4
```

### Development Setup

```bash
# Enable auto-reload and detailed errors
codebot serve --port 5000 --debug
```

## Troubleshooting

For token validation issues, GitHub Enterprise setup problems, and other configuration troubleshooting, see the [Troubleshooting Guide](troubleshooting.md).

## Next Steps

- [CLI Usage Guide](cli-usage.md) - Run tasks from command line
- [HTTP API Guide](http-api.md) - Programmatic task submission
- [Webhooks Guide](webhooks.md) - PR review automation

---

[← Back to Documentation](index.md)
