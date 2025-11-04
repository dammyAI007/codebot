# Examples

Practical examples and recipes for using Codebot.

## CLI Examples

### Simple Bug Fix

**task.yaml:**
```yaml
repository_url: https://github.com/user/myproject.git
description: Fix the null pointer exception in UserService.java
```

**Run:**
```bash
codebot run --task-prompt-file task.yaml
```

### Feature with Ticket ID

**task.yaml:**
```yaml
repository_url: https://github.com/user/myproject.git
ticket_id: FEA-456
ticket_summary: add-dark-mode
description: |
  Add dark mode support to the application.
  Include a toggle in the settings page.
  Ensure all existing tests still pass.
```

**Run:**
```bash
codebot run --task-prompt-file task.yaml
```

### Custom Base Branch

**task.yaml:**
```yaml
repository_url: https://github.com/user/myproject.git
base_branch: develop
description: Backport security fix to develop branch
```

**Run:**
```bash
codebot run --task-prompt-file task.yaml
```

### Inline JSON Task

```bash
codebot run --task-prompt '{
  "repository_url": "https://github.com/user/repo.git",
  "description": "Add README with installation instructions"
}'
```

## HTTP API Examples

### Submit Task (curl)

```bash
curl -X POST http://localhost:5000/api/tasks/submit \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "repository_url": "https://github.com/user/repo.git",
    "description": "Add dark mode support",
    "ticket_id": "FEAT-123"
  }'
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Task queued successfully"
}
```

### Check Task Status

```bash
curl http://localhost:5000/api/tasks/550e8400-e29b-41d4-a716-446655440000/status \
  -H "Authorization: Bearer your-api-key"
```

**Response:**
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

### List Completed Tasks

```bash
curl "http://localhost:5000/api/tasks?status=completed&limit=10" \
  -H "Authorization: Bearer your-api-key"
```

## Next Steps

- [CLI Usage Guide](cli-usage.md) - Learn CLI commands
- [HTTP API Guide](http-api.md) - API reference
- [Webhooks Guide](webhooks.md) - PR automation

---

[← Back to Documentation](index.md)
