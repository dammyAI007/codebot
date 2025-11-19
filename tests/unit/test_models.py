"""Tests for codebot.core.models module."""

import pytest
from datetime import datetime

from codebot.core.models import Task, TaskPrompt


class TestTaskPrompt:
    """Tests for TaskPrompt dataclass."""
    
    def test_create_task_prompt_with_required_fields(self):
        """Test creating TaskPrompt with only required fields."""
        prompt = TaskPrompt(
            repository_url="https://github.com/test/repo",
            description="Test description",
        )
        
        assert prompt.repository_url == "https://github.com/test/repo"
        assert prompt.description == "Test description"
        assert prompt.ticket_id is None
        assert prompt.ticket_summary is None
        assert prompt.test_command is None
        assert prompt.base_branch is None
    
    def test_create_task_prompt_with_all_fields(self, sample_task_prompt_data):
        """Test creating TaskPrompt with all fields."""
        prompt = TaskPrompt(**sample_task_prompt_data)
        
        assert prompt.repository_url == "https://github.com/test/repo"
        assert prompt.description == "Test task description"
        assert prompt.ticket_id == "TASK-123"
        assert prompt.ticket_summary == "Test ticket summary"
        assert prompt.test_command == "pytest"
        assert prompt.base_branch == "main"
    
    def test_task_prompt_missing_repository_url(self):
        """Test that TaskPrompt raises ValueError when repository_url is missing."""
        with pytest.raises(ValueError, match="repository_url is required"):
            TaskPrompt(repository_url="", description="Test")
    
    def test_task_prompt_missing_description(self):
        """Test that TaskPrompt raises ValueError when description is missing."""
        with pytest.raises(ValueError, match="description is required"):
            TaskPrompt(repository_url="https://github.com/test/repo", description="")
    
    def test_task_prompt_with_none_repository_url(self):
        """Test that TaskPrompt raises ValueError when repository_url is None."""
        with pytest.raises(ValueError, match="repository_url is required"):
            TaskPrompt(repository_url=None, description="Test")
    
    def test_task_prompt_with_none_description(self):
        """Test that TaskPrompt raises ValueError when description is None."""
        with pytest.raises(ValueError, match="description is required"):
            TaskPrompt(repository_url="https://github.com/test/repo", description=None)


class TestTask:
    """Tests for Task dataclass."""
    
    def test_create_task_with_required_fields(self, sample_task_prompt):
        """Test creating Task with required fields."""
        submitted_at = datetime(2024, 1, 1, 12, 0, 0)
        
        task = Task(
            id="task-123",
            prompt=sample_task_prompt,
            status="pending",
            submitted_at=submitted_at,
        )
        
        assert task.id == "task-123"
        assert task.prompt == sample_task_prompt
        assert task.status == "pending"
        assert task.submitted_at == submitted_at
        assert task.source == "web"  # default value
        assert task.started_at is None
        assert task.completed_at is None
        assert task.result is None
        assert task.error is None
        assert task.subtasks == []
        assert task.logs is None
    
    def test_create_task_with_all_fields(self, sample_task_prompt):
        """Test creating Task with all fields."""
        submitted_at = datetime(2024, 1, 1, 12, 0, 0)
        started_at = datetime(2024, 1, 1, 12, 5, 0)
        completed_at = datetime(2024, 1, 1, 12, 30, 0)
        
        subtask = Task(
            id="subtask-1",
            prompt=sample_task_prompt,
            status="completed",
            submitted_at=submitted_at,
        )
        
        task = Task(
            id="task-123",
            prompt=sample_task_prompt,
            status="completed",
            submitted_at=submitted_at,
            source="cli",
            started_at=started_at,
            completed_at=completed_at,
            result={"pr_url": "https://github.com/test/repo/pull/1"},
            error=None,
            subtasks=[subtask],
            logs=[{"level": "info", "message": "Test log"}],
        )
        
        assert task.id == "task-123"
        assert task.status == "completed"
        assert task.source == "cli"
        assert task.started_at == started_at
        assert task.completed_at == completed_at
        assert task.result == {"pr_url": "https://github.com/test/repo/pull/1"}
        assert task.error is None
        assert len(task.subtasks) == 1
        assert task.subtasks[0].id == "subtask-1"
        assert task.logs == [{"level": "info", "message": "Test log"}]
    
    def test_task_with_error(self, sample_task_prompt):
        """Test creating Task with error."""
        submitted_at = datetime(2024, 1, 1, 12, 0, 0)
        
        task = Task(
            id="task-123",
            prompt=sample_task_prompt,
            status="failed",
            submitted_at=submitted_at,
            error="Something went wrong",
        )
        
        assert task.status == "failed"
        assert task.error == "Something went wrong"
        assert task.result is None
    
    def test_task_default_subtasks_list(self, sample_task_prompt):
        """Test that subtasks defaults to empty list."""
        task = Task(
            id="task-123",
            prompt=sample_task_prompt,
            status="pending",
            submitted_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        
        assert task.subtasks == []
        assert isinstance(task.subtasks, list)
    
    def test_task_status_values(self, sample_task_prompt):
        """Test various task status values."""
        statuses = ["pending", "running", "completed", "failed", "rejected"]
        
        for status in statuses:
            task = Task(
                id=f"task-{status}",
                prompt=sample_task_prompt,
                status=status,
                submitted_at=datetime(2024, 1, 1, 12, 0, 0),
            )
            assert task.status == status
    
    def test_task_source_values(self, sample_task_prompt):
        """Test various task source values."""
        sources = ["web", "cli", "webhook", "review"]
        
        for source in sources:
            task = Task(
                id=f"task-{source}",
                prompt=sample_task_prompt,
                status="pending",
                submitted_at=datetime(2024, 1, 1, 12, 0, 0),
                source=source,
            )
            assert task.source == source
