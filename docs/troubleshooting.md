# Troubleshooting Guide

Common issues and solutions for Codebot setup, configuration, and usage.

## Installation Issues

### Command not found: codebot

**Problem**: `codebot: command not found` when trying to run codebot.

**Solutions**:
1. Use `uv run` if you haven't activated the virtual environment:
   ```bash
   uv run codebot --help
   ```

2. Or activate the virtual environment first:
   ```bash
   source .venv/bin/activate
   codebot --help
   ```

### Claude Code CLI not found

**Problem**: Claude Code CLI is not installed or not in PATH.

**Solutions**:
1. Check if Claude Code CLI is installed:
   ```bash
   which claude
   claude --version
   ```

2. If not found, install following the [official documentation](https://www.anthropic.com/claude/docs/claude-code).

## GitHub App Configuration Issues

### GitHub App configuration validation failed

**Problem**: "Invalid GitHub App configuration" or authentication errors.

**Solutions**:
1. **Verify all required environment variables are set**
   - `GITHUB_APP_ID` - Must be a numeric value
   - `GITHUB_APP_PRIVATE_KEY_PATH` - Path to the private key file
   - `GITHUB_APP_INSTALLATION_ID` - Must be a numeric value

2. **Check private key file**
   - Ensure the file exists at the specified path
   - Verify the file is readable by the codebot process
   - Check that the file is a valid PEM format private key
   - Ensure the file hasn't been corrupted

3. **Verify GitHub App ID**
   - Check that the App ID matches your GitHub App
   - Find it in your GitHub App settings page

4. **Verify Installation ID**
   - Check that the installation ID is correct
   - Find it in the GitHub App installation URL or via API:
     ```bash
     curl -H "Authorization: Bearer YOUR_JWT" https://api.github.com/app/installations
     ```
   - Ensure the app is installed on the repositories you're trying to access

5. **For GitHub Enterprise**:
   - Ensure `GITHUB_ENTERPRISE_URL` or `GITHUB_API_URL` is set correctly
   - Verify the API URL format: `https://github.company.com/api/v3`
   - Ensure you're using the correct GitHub App from the enterprise instance

### Invalid GitHub App configuration (CLI tasks)

**Problem**: Task fails with "Invalid GitHub App configuration" error.

**Solutions**:
1. Ensure all three required environment variables are set:
   - `GITHUB_APP_ID`
   - `GITHUB_APP_PRIVATE_KEY_PATH`
   - `GITHUB_APP_INSTALLATION_ID`

2. Verify the private key file path is correct and the file exists

3. Check that the GitHub App has the required permissions:
   - Contents: Read and Write
   - Pull requests: Read and Write
   - Metadata: Read-only

4. Ensure the GitHub App is installed on the repositories you're accessing

5. Run with `--verbose` flag for detailed debugging information

6. See [Configuration Guide](configuration.md) for detailed GitHub App setup

### PR creation fails

**Problem**: Pull request creation fails despite successful code changes.

**Solutions**:
1. **Verify token permissions**:
   - GitHub token needs `repo` or `pull_requests: write` permission
   - For fine-grained tokens, ensure "Pull requests: Write" is enabled

2. **Check repository access**:
   - Verify repository URL is correct in task file
   - Ensure you have push access to the repository
   - For GitHub Enterprise, verify the URL format and token

3. **Test repository access**:
   ```bash
   git clone YOUR_REPO_URL
   ```

## Server and API Issues

### 401 Unauthorized (HTTP API)

**Problem**: API requests return 401 Unauthorized.

**Solutions**:
1. **Verify API key is correct**
   - Check `CODEBOT_API_KEYS` is set on server
   - Ensure API key matches exactly (no extra spaces)

2. **Check Authorization header format**:
   ```bash
   # Correct formats:
   Authorization: Bearer your-api-key
   X-API-Key: your-api-key
   ```

3. **Restart server after changing keys**

### Task stuck in pending

**Problem**: Tasks remain in "pending" status and never execute.

**Solutions**:
1. **Check worker threads are running**
   - Verify `--workers` is > 0 when starting server
   - Check `CODEBOT_MAX_WORKERS` environment variable

2. **Check server logs for errors**
   - Look for worker thread startup messages
   - Check for GitHub token validation errors

3. **Verify sufficient system resources**
   - Ensure enough memory and CPU for worker threads

### Task failed

**Problem**: Task shows "failed" status in API response.

**Solutions**:
1. **Check error field in status response**
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:5000/api/tasks/TASK_ID/status
   ```

2. **Common failure reasons**:
   - GitHub token lacks correct permissions
   - Repository URL is inaccessible
   - Claude Code CLI errors
   - Git operations failed

3. **Check server logs** for detailed error messages

## Webhook Issues

### Webhook not receiving events

**Problem**: GitHub webhook events are not being received by codebot server.

**Solutions**:
1. **Check webhook configuration in GitHub**
   - Go to repository Settings → Webhooks
   - Verify payload URL is correct
   - Check "Recent Deliveries" for delivery status

2. **Verify webhook secret matches**
   - Ensure `GITHUB_WEBHOOK_SECRET` environment variable matches GitHub webhook secret

3. **Check webhook events**
   - Ensure "Pull request review comments" and "Pull request reviews" are enabled

4. **Test webhook delivery**
   - Use "Redeliver" button in GitHub webhook settings
   - Check server logs for incoming requests

### Signature verification failed

**Problem**: Webhook signature verification fails.

**Solutions**:
1. **Ensure webhook secret matches exactly**
   - `GITHUB_WEBHOOK_SECRET` must match GitHub webhook secret
   - Check for extra whitespace in environment variable

2. **Verify content type**
   - Webhook must use `application/json` content type
   - Check GitHub webhook configuration

3. **Check webhook secret setup**
   ```bash
   echo "GITHUB_WEBHOOK_SECRET=$GITHUB_WEBHOOK_SECRET"
   ```

### Comments not being processed

**Problem**: Webhook receives events but comments are not processed.

**Solutions**:
1. **Check server logs for errors**
   - Look for review processor thread errors
   - Check for GitHub API errors

2. **Verify GitHub token permissions**
   - Token needs read access to PR details and comments
   - Token needs write access to post comments

3. **Ensure review processor thread is running**
   - Check server startup logs
   - Verify worker threads are active

### Codebot responding to its own comments

**Problem**: Infinite loop where codebot responds to its own comments.

**Solutions**:
1. **Check comment signature detection**
   - Codebot should detect its own signature in comment body
   - Look for "🤖 Generated with Claude Code" in comments

2. **Verify recursion prevention logic**
   - Check server logs for comment filtering
   - May need to update filter logic if signature format changed

## Task Execution Issues

### Changes not committed

**Problem**: Claude Code CLI runs but changes are not committed to git.

**Solutions**:
1. **Check task description clarity**
   - Ensure task description is clear and actionable
   - Claude needs specific, well-defined tasks

2. **Verify git configuration**
   - Check git user.name and user.email are set
   - Ensure working directory has git repository

3. **Check Claude Code CLI output**
   - Look for error messages in CLI output
   - Verify Claude completed the task successfully

### Git push fails

**Problem**: Changes are committed but git push fails with authentication errors.

**Solutions**:
1. **For GitHub Enterprise**:
   - Ensure `GITHUB_ENTERPRISE_URL` is set correctly
   - Verify token is from the enterprise instance

2. **Check token permissions**:
   - Token needs push access to repository
   - For private repos, ensure `repo` scope is enabled

3. **Test git access manually**:
   ```bash
   git clone YOUR_REPO_URL
   cd YOUR_REPO
   # Make a test change
   git add .
   git commit -m "test"
   git push
   ```

## Configuration Issues

### Worker threads not starting

**Problem**: Server starts but worker threads don't start processing tasks.

**Solutions**:
1. **Check `CODEBOT_MAX_WORKERS` value**
   - Must be > 0
   - Recommended range: 1-10

2. **Verify sufficient system resources**
   - Each worker thread needs memory and CPU
   - Check system resource usage

3. **Check server logs for errors**
   - Look for worker thread initialization errors
   - Check for configuration validation errors

### Environment variables not loading

**Problem**: Environment variables from `.env` file are not being loaded.

**Solutions**:
1. **Check `.env` file location**
   - Must be in the current working directory when starting codebot
   - Or in the project root directory

2. **Verify `.env` file format**:
   ```bash
   # Correct format (no quotes needed):
   GITHUB_APP_ID=123456
   GITHUB_APP_PRIVATE_KEY_PATH=./codebot-private-key.pem
   GITHUB_APP_INSTALLATION_ID=789012
   GITHUB_ENTERPRISE_URL=https://github.company.com
   ```

3. **Check for syntax errors in `.env` file**
   - No spaces around `=`
   - No quotes unless the value contains spaces

## Debugging Tips

### Enable verbose logging

For CLI tasks:
```bash
codebot run --task-prompt-file task.yaml --verbose
```

### Check server health

```bash
curl http://localhost:5000/health
```

### View detailed task status

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:5000/api/tasks/TASK_ID/status
```

### Monitor server logs

```bash
# When running server with debug mode
codebot serve --debug

# Check for specific error patterns
tail -f server.log | grep -E "(ERROR|WARN|Failed)"
```

### Test GitHub API access

```bash
# Test token validation
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user

# For GitHub Enterprise
curl -H "Authorization: token YOUR_TOKEN" https://github.company.com/api/v3/user
```

## Getting Help

If you're still experiencing issues:

1. **Check server logs** for detailed error messages
2. **Run with verbose logging** to see detailed debugging information
3. **Test components individually** (GitHub token, Claude CLI, git access)
4. **Verify environment variables** are set correctly
5. **Check GitHub webhook delivery logs** for webhook issues

## Related Documentation

- [Configuration Guide](configuration.md) - Environment variables and settings
- [Installation Guide](installation.md) - Setup and installation
- [CLI Usage Guide](cli-usage.md) - Command-line interface
- [HTTP API Guide](http-api.md) - Programmatic task submission
- [Webhooks Guide](webhooks.md) - PR review automation

---

[← Back to Documentation](index.md)