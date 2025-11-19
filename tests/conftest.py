"""Shared pytest fixtures for codebot tests."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_task_prompt_data():
    """Sample task prompt data for testing."""
    return {
        "repository_url": "https://github.com/test/repo",
        "description": "Test task description",
        "ticket_id": "TASK-123",
        "ticket_summary": "Test ticket summary",
        "test_command": "pytest",
        "base_branch": "main",
    }


@pytest.fixture
def sample_task_prompt(sample_task_prompt_data):
    """Sample TaskPrompt instance."""
    from codebot.core.models import TaskPrompt
    return TaskPrompt(**sample_task_prompt_data)


@pytest.fixture
def sample_task(sample_task_prompt):
    """Sample Task instance."""
    from codebot.core.models import Task
    return Task(
        id="test-task-123",
        prompt=sample_task_prompt,
        status="pending",
        submitted_at=datetime(2024, 1, 1, 12, 0, 0),
        source="web",
    )


@pytest.fixture
def mock_github_app_auth(mocker):
    """Mock GitHubAppAuth for testing."""
    mock = mocker.MagicMock()
    mock.get_installation_token.return_value = "ghs_test_token_123"
    mock.api_url = "https://api.github.com"
    mock.bot_user_id = "123456"
    mock.bot_name = "test-bot"
    return mock


@pytest.fixture
def mock_subprocess_run(mocker):
    """Mock subprocess.run for testing."""
    mock = mocker.patch("subprocess.run")
    mock.return_value = MagicMock(
        returncode=0,
        stdout="",
        stderr="",
    )
    return mock


@pytest.fixture
def temp_workspace(tmp_path) -> Path:
    """Create a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def mock_git_repo(temp_workspace):
    """Create a mock git repository structure."""
    git_dir = temp_workspace / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
    return temp_workspace


@pytest.fixture
def in_memory_db() -> Generator[sqlite3.Connection, None, None]:
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def mock_requests(requests_mock):
    """Provide requests_mock fixture with common GitHub API mocks."""
    # Mock common GitHub API endpoints
    requests_mock.get(
        "https://api.github.com/app/installations",
        json=[{"id": 12345}],
    )
    return requests_mock


@pytest.fixture
def flask_test_app():
    """Create a Flask test app instance."""
    from codebot.server.flask_app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture
def flask_client(flask_test_app):
    """Create a Flask test client."""
    return flask_test_app.test_client()
