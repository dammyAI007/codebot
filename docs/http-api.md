# HTTP API Guide

Codebot provides a REST API for programmatic task submission with async execution and status tracking.

## Overview

The HTTP API allows you to:
- Submit tasks programmatically from any client
- Track task progress and results
- Scale execution with multiple worker threads
- Integrate codebot into your CI/CD pipelines

## Setup

### 1. Set API Keys

Create one or more API keys (comma-separated for multiple):

```bash
export CODEBOT_API_KEYS="secret-key-1,secret-key-2"
```

Or in `.env` file:

```
CODEBOT_API_KEYS=secret-key-1,secret-key-2
```

### 2. Start Server

```bash
codebot serve --port 5000 --workers 2
```

Options:
- `--port` - Server port (default: 5000)
- `--workers` - Number of task processor threads (default: 1)
- `--work-dir` - Base directory for workspaces
- `--debug` - Enable debug mode with auto-reload

**Note**: GitHub App configuration is required via environment variables:
- `GITHUB_APP_ID` - GitHub App ID
- `GITHUB_APP_PRIVATE_KEY_PATH` - Path to private key file
- `GITHUB_APP_INSTALLATION_ID` - Installation ID

The server will display:

```
HTTP API enabled with 2 API key(s)
Starting server on port 5000...
API endpoints: http://localhost:5000/api/tasks/submit
               http://localhost:5000/api/tasks/{task_id}/status
               http://localhost:5000/api/tasks
```

## Authentication

All API endpoints require authentication using an API key.

### Authorization Header

```bash
curl -H "Authorization: Bearer your-api-key" ...
```

## Endpoints

### POST /api/tasks/submit

Submit a new task for async execution.

**Request:**

```bash
curl -X POST http://localhost:5000/api/tasks/submit \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "repository_url": "https://github.com/user/repo.git",
    "description": "Add dark mode support to the application",
    "ticket_id": "FEAT-123",
    "ticket_summary": "add-dark-mode"
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `repository_url` | string | ✅ | Git URL to clone |
| `description` | string | ✅ | Task description for Claude |
| `ticket_id` | string | ❌ | External ticket/issue ID |
| `ticket_summary` | string | ❌ | Short name for the ticket |
| `test_command` | string | ❌ | Override test command |
| `base_branch` | string | ❌ | Branch to checkout from |

**Response (202 Accepted):**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Task queued successfully"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid request body or missing required fields
- `401 Unauthorized` - Invalid or missing API key
- `500 Internal Server Error` - Server error

### GET /api/tasks/{task_id}/status

Check the status and results of a task.

**Request:**

```bash
curl http://localhost:5000/api/tasks/550e8400-e29b-41d4-a716-446655440000/status \
  -H "Authorization: Bearer your-api-key"
```

**Response (200 OK):**

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

**Status Values:**

- `pending` - Task is queued, waiting to be processed
- `running` - Task is currently being executed
- `completed` - Task finished successfully
- `failed` - Task failed with an error

**Failed Task Response:**

```json
{
  "task_id": "...",
  "status": "failed",
  "submitted_at": "2025-11-03T12:00:00Z",
  "started_at": "2025-11-03T12:00:05Z",
  "completed_at": "2025-11-03T12:01:30Z",
  "error": "Failed to clone repository: authentication failed"
}
```

**Error Responses:**

- `404 Not Found` - Task ID not found
- `401 Unauthorized` - Invalid or missing API key

### GET /api/tasks

List recent tasks with optional filtering.

**Request:**

```bash
curl "http://localhost:5000/api/tasks?status=completed&limit=10" \
  -H "Authorization: Bearer your-api-key"
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `pending`, `running`, `completed`, `failed` |
| `limit` | integer | Max results (1-1000, default: 100) |

**Response (200 OK):**

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

**Error Responses:**

- `400 Bad Request` - Invalid query parameters
- `401 Unauthorized` - Invalid or missing API key

## Features

### Async Execution

Tasks are queued and processed in the background. Submit a task and poll for status:

```bash
# Submit task
TASK_ID=$(curl -X POST http://localhost:5000/api/tasks/submit \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"repository_url": "...", "description": "..."}' \
  | jq -r '.task_id')

# Poll for completion
while true; do
  STATUS=$(curl -s http://localhost:5000/api/tasks/$TASK_ID/status \
    -H "Authorization: Bearer your-api-key" \
    | jq -r '.status')
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  
  echo "Status: $STATUS"
  sleep 5
done

echo "Final status: $STATUS"
```

### Scalable Workers

Configure multiple worker threads to process tasks in parallel:

```bash
codebot serve --port 5000 --workers 4
```

This allows up to 4 tasks to run simultaneously.

### Separate Queues

The HTTP API uses a separate task queue from webhook review comments, allowing independent scaling and prioritization.

## Configuration

Environment variables for the HTTP API:

| Variable | Description | Default |
|----------|-------------|---------|
| `CODEBOT_API_KEYS` | Comma-separated API keys | (required) |
| `CODEBOT_MAX_WORKERS` | Maximum worker threads | 1 |
| `CODEBOT_MAX_QUEUE_SIZE` | Maximum tasks in queue | 100 |
| `CODEBOT_TASK_RETENTION` | Task data retention (seconds) | 86400 (24h) |

See [Configuration Guide](configuration.md) for details.

## Health Check

Check server health and queue status:

```bash
curl http://localhost:5000/health
```

Response:

```json
{
  "status": "healthy",
  "review_queue_size": 0,
  "task_queue_size": 2
}
```

## Troubleshooting

For API errors, task issues, and server problems, see the [Troubleshooting Guide](troubleshooting.md).

## Next Steps

- [Configuration Guide](configuration.md) - Advanced settings
- [Webhooks Guide](webhooks.md) - PR review automation
- [Examples](examples.md) - More integration examples

---

[← Back to Documentation](index.md)

