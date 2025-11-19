"""Tests for API endpoints in codebot.server.api module."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from flask import Flask

from codebot.server.api import create_api_blueprint
from codebot.server.task_queue import TaskQueue
from codebot.core.models import Task, TaskPrompt


@pytest.fixture
def test_app():
    """Create a test Flask app with API blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    
    # Create a mock task queue
    mock_queue = MagicMock(spec=TaskQueue)
    mock_queue.enqueue = MagicMock()
    mock_queue.get_task = MagicMock(return_value=None)
    mock_queue.list_tasks = MagicMock(return_value=[])
    
    # Create API blueprint with the mock queue
    api_blueprint = create_api_blueprint(mock_queue)
    app.register_blueprint(api_blueprint, url_prefix="/api")
    
    # Store mock queue on app for test access
    app.task_queue = mock_queue
    
    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return test_app.test_client()


@pytest.fixture(autouse=True)
def mock_auth():
    """Mock authentication for all tests."""
    with patch("codebot.server.auth.config") as mock_config:
        mock_config.is_api_key_valid.return_value = True
        mock_config.has_web_auth.return_value = False
        yield mock_config


class TestTaskSubmitEndpoint:
    """Tests for /api/tasks/submit endpoint."""
    
    def test_submit_task_with_valid_data(self, client):
        """Test submitting a task with valid data."""
        response = client.post(
            "/api/tasks/submit",
            headers={"Authorization": "Bearer test-api-key"},
            json={
                "repository_url": "https://github.com/test/repo",
                "description": "Fix bug in login",
            }
        )
        
        assert response.status_code == 202
        data = response.json
        assert "task_id" in data
    
    def test_submit_task_with_all_fields(self, client):
        """Test submitting task with all optional fields."""
        response = client.post(
            "/api/tasks/submit",
            headers={"Authorization": "Bearer test-api-key"},
            json={
                "repository_url": "https://github.com/test/repo",
                "description": "Add new feature",
                "ticket_id": "TASK-123",
                "ticket_summary": "Add user authentication",
                "test_command": "pytest tests/",
                "base_branch": "develop",
            }
        )
        
        assert response.status_code == 202
    
    def test_submit_task_missing_repository_url(self, client):
        """Test submitting task without repository URL."""
        response = client.post(
            "/api/tasks/submit",
            headers={"Authorization": "Bearer test-api-key"},
            json={"description": "Fix bug"}
        )
        
        assert response.status_code == 400
    
    def test_submit_task_missing_description(self, client):
        """Test submitting task without description."""
        response = client.post(
            "/api/tasks/submit",
            headers={"Authorization": "Bearer test-api-key"},
            json={"repository_url": "https://github.com/test/repo"}
        )
        
        assert response.status_code == 400
    
    def test_submit_task_without_authentication(self, client):
        """Test submitting task without authentication."""
        response = client.post(
            "/api/tasks/submit",
            json={
                "repository_url": "https://github.com/test/repo",
                "description": "Fix bug",
            }
        )
        
        assert response.status_code == 401
    
    def test_submit_task_with_invalid_json(self, client):
        """Test submitting task with invalid JSON."""
        response = client.post(
            "/api/tasks/submit",
            headers={
                "Authorization": "Bearer test-api-key",
                "Content-Type": "application/json",
            },
            data="not valid json"
        )
        
        # Flask returns 400 for bad JSON, or 500 if not handled
        assert response.status_code in [400, 500]


class TestTaskStatusEndpoint:
    """Tests for /api/tasks/<task_id>/status endpoint."""
    
    def test_get_task_status(self, client, test_app):
        """Test getting task status."""
        mock_task = Task(
            id="task-123",
            prompt=TaskPrompt(
                repository_url="https://github.com/test/repo",
                description="Test task"
            ),
            status="running",
            submitted_at=datetime(2024, 1, 1, 12, 0, 0),
            source="web"
        )
        test_app.task_queue.get_task = MagicMock(return_value=mock_task)
        
        response = client.get(
            "/api/tasks/task-123/status",
            headers={"Authorization": "Bearer test-api-key"}
        )
        
        assert response.status_code == 200
        data = response.json
        assert data["task_id"] == "task-123"
    
    def test_get_nonexistent_task_status(self, client, test_app):
        """Test getting status of nonexistent task."""
        test_app.task_queue.get_task = MagicMock(return_value=None)
        
        response = client.get(
            "/api/tasks/nonexistent/status",
            headers={"Authorization": "Bearer test-api-key"}
        )
        
        assert response.status_code == 404
    
    def test_get_task_status_without_authentication(self, client):
        """Test getting task status without authentication."""
        response = client.get("/api/tasks/task-123/status")
        assert response.status_code == 401


class TestListTasksEndpoint:
    """Tests for /api/tasks endpoint."""
    
    def test_list_tasks(self, client, test_app):
        """Test listing all tasks."""
        mock_tasks = [
            Task(
                id="task-1",
                prompt=TaskPrompt(
                    repository_url="https://github.com/test/repo1",
                    description="Task 1"
                ),
                status="completed",
                submitted_at=datetime(2024, 1, 1, 12, 0, 0),
                source="web"
            ),
        ]
        test_app.task_queue.list_tasks = MagicMock(return_value=mock_tasks)
        
        response = client.get(
            "/api/tasks",
            headers={"Authorization": "Bearer test-api-key"}
        )
        
        assert response.status_code == 200
        data = response.json
        assert "tasks" in data
    
    def test_list_tasks_with_status_filter(self, client, test_app):
        """Test listing tasks with status filter."""
        mock_tasks = []
        test_app.task_queue.list_tasks = MagicMock(return_value=mock_tasks)
        
        response = client.get(
            "/api/tasks?status=completed",
            headers={"Authorization": "Bearer test-api-key"}
        )
        
        assert response.status_code == 200


class TestHealthCheckEndpoint:
    """Tests for health check endpoint."""
    
    @pytest.mark.skip(reason="Health check endpoint not implemented")
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
