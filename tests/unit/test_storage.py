"""Tests for codebot.core.storage_sqlite module."""

import json
import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from codebot.core.models import Task, TaskPrompt
from codebot.core.storage_sqlite import SQLiteTaskStorage


@pytest.fixture
def storage_db(tmp_path):
    """Create a temporary SQLite storage instance."""
    db_path = tmp_path / "test_tasks.db"
    storage = SQLiteTaskStorage(db_path)
    yield storage
    storage.close()


@pytest.fixture
def sample_stored_task(storage_db, sample_task):
    """Add a sample task to storage and return it."""
    storage_db.add_task(sample_task)
    return sample_task


class TestSQLiteTaskStorage:
    """Tests for SQLiteTaskStorage class."""
    
    def test_create_storage_creates_db_file(self, tmp_path):
        """Test that creating storage creates database file."""
        db_path = tmp_path / "tasks.db"
        storage = SQLiteTaskStorage(db_path)
        
        assert db_path.exists()
        storage.close()
    
    def test_create_storage_creates_schema(self, storage_db):
        """Test that schema is created."""
        cursor = storage_db.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='tasks'
        """)
        
        assert cursor.fetchone() is not None
    
    def test_add_task(self, storage_db, sample_task):
        """Test adding a task to storage."""
        storage_db.add_task(sample_task)
        
        cursor = storage_db.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (sample_task.id,))
        row = cursor.fetchone()
        
        assert row is not None
        assert row["id"] == sample_task.id
        assert row["status"] == "pending"
    
    def test_get_task(self, storage_db, sample_stored_task):
        """Test retrieving a task by ID."""
        task = storage_db.get_task(sample_stored_task.id)
        
        assert task is not None
        assert task.id == sample_stored_task.id
        assert task.status == sample_stored_task.status
        assert task.prompt.repository_url == sample_stored_task.prompt.repository_url
    
    def test_get_nonexistent_task(self, storage_db):
        """Test that getting nonexistent task returns None."""
        task = storage_db.get_task("nonexistent")
        
        assert task is None
    
    def test_update_task_status(self, storage_db, sample_stored_task):
        """Test updating task status."""
        storage_db.update_task(sample_stored_task.id, status="running")
        
        task = storage_db.get_task(sample_stored_task.id)
        assert task.status == "running"
    
    def test_update_task_with_result(self, storage_db, sample_stored_task):
        """Test updating task with result."""
        result = {"pr_url": "https://github.com/test/repo/pull/1"}
        completed_at = datetime(2024, 1, 1, 13, 0, 0)
        
        storage_db.update_task(
            sample_stored_task.id,
            status="completed",
            completed_at=completed_at,
            result=result,
        )
        
        task = storage_db.get_task(sample_stored_task.id)
        assert task.status == "completed"
        assert task.completed_at == completed_at
        assert task.result == result
    
    def test_update_task_with_error(self, storage_db, sample_stored_task):
        """Test updating task with error."""
        storage_db.update_task(
            sample_stored_task.id,
            status="failed",
            error="Something went wrong",
        )
        
        task = storage_db.get_task(sample_stored_task.id)
        assert task.status == "failed"
        assert task.error == "Something went wrong"
    
    def test_list_tasks(self, storage_db, sample_task_prompt):
        """Test listing tasks."""
        task1 = Task(
            id="task-1",
            prompt=sample_task_prompt,
            status="pending",
            submitted_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        task2 = Task(
            id="task-2",
            prompt=sample_task_prompt,
            status="completed",
            submitted_at=datetime(2024, 1, 1, 13, 0, 0),
        )
        
        storage_db.add_task(task1)
        storage_db.add_task(task2)
        
        tasks = storage_db.list_tasks()
        
        assert len(tasks) == 2
        assert tasks[0].id == "task-2"  # Most recent first
        assert tasks[1].id == "task-1"
    
    def test_list_tasks_with_status_filter(self, storage_db, sample_task_prompt):
        """Test listing tasks with status filter."""
        task1 = Task(
            id="task-1",
            prompt=sample_task_prompt,
            status="pending",
            submitted_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        task2 = Task(
            id="task-2",
            prompt=sample_task_prompt,
            status="completed",
            submitted_at=datetime(2024, 1, 1, 13, 0, 0),
        )
        
        storage_db.add_task(task1)
        storage_db.add_task(task2)
        
        completed_tasks = storage_db.list_tasks(status_filter="completed")
        
        assert len(completed_tasks) == 1
        assert completed_tasks[0].id == "task-2"
    
    def test_list_tasks_with_source_filter(self, storage_db, sample_task_prompt):
        """Test listing tasks with source filter."""
        task1 = Task(
            id="task-1",
            prompt=sample_task_prompt,
            status="pending",
            submitted_at=datetime(2024, 1, 1, 12, 0, 0),
            source="web",
        )
        task2 = Task(
            id="task-2",
            prompt=sample_task_prompt,
            status="pending",
            submitted_at=datetime(2024, 1, 1, 13, 0, 0),
            source="cli",
        )
        
        storage_db.add_task(task1)
        storage_db.add_task(task2)
        
        cli_tasks = storage_db.list_tasks(source_filter="cli")
        
        assert len(cli_tasks) == 1
        assert cli_tasks[0].id == "task-2"
    
    def test_add_task_with_subtasks(self, storage_db, sample_task_prompt):
        """Test adding task with subtasks."""
        subtask = Task(
            id="subtask-1",
            prompt=sample_task_prompt,
            status="completed",
            submitted_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        
        parent_task = Task(
            id="parent-1",
            prompt=sample_task_prompt,
            status="running",
            submitted_at=datetime(2024, 1, 1, 12, 0, 0),
            subtasks=[subtask],
        )
        
        storage_db.add_task(parent_task)
        
        retrieved_task = storage_db.get_task("parent-1")
        assert len(retrieved_task.subtasks) == 1
        assert retrieved_task.subtasks[0].id == "subtask-1"
    
    def test_find_task_by_branch_uuid(self, storage_db, sample_task_prompt):
        """Test finding task by branch UUID."""
        task = Task(
            id="task-1",
            prompt=sample_task_prompt,
            status="completed",
            submitted_at=datetime(2024, 1, 1, 12, 0, 0),
            result={
                "branch_name": "u/codebot/TASK-123/abc1234/feature",
                "pr_url": "https://github.com/test/repo/pull/1",
            },
        )
        
        storage_db.add_task(task)
        
        found_task = storage_db.find_task_by_branch_uuid("abc1234")
        
        assert found_task is not None
        assert found_task.id == "task-1"
    
    def test_find_task_by_pr_url(self, storage_db, sample_task_prompt):
        """Test finding task by PR URL."""
        pr_url = "https://github.com/test/repo/pull/42"
        task = Task(
            id="task-1",
            prompt=sample_task_prompt,
            status="completed",
            submitted_at=datetime(2024, 1, 1, 12, 0, 0),
            result={"pr_url": pr_url},
        )
        
        storage_db.add_task(task)
        
        found_task = storage_db.find_task_by_pr_url(pr_url)
        
        assert found_task is not None
        assert found_task.id == "task-1"
    
    def test_update_task_logs(self, storage_db, sample_stored_task):
        """Test updating task logs."""
        logs = [
            {"level": "info", "message": "Starting task", "timestamp": "2024-01-01T12:00:00"},
            {"level": "info", "message": "Task completed", "timestamp": "2024-01-01T12:30:00"},
        ]
        
        storage_db.update_task_logs(sample_stored_task.id, logs)
        
        task = storage_db.get_task(sample_stored_task.id)
        assert task.logs == logs
    
    def test_is_comment_processed(self, storage_db):
        """Test checking if comment is processed."""
        assert storage_db.is_comment_processed(123, "owner", "repo", 1, "review_comment") is False
        
        storage_db.mark_comment_processed(123, "owner", "repo", 1, "review_comment")
        
        assert storage_db.is_comment_processed(123, "owner", "repo", 1, "review_comment") is True
    
    def test_mark_comment_processed(self, storage_db):
        """Test marking comment as processed."""
        storage_db.mark_comment_processed(456, "owner", "repo", 2, "issue_comment")
        
        cursor = storage_db.conn.cursor()
        cursor.execute("""
            SELECT * FROM processed_comments
            WHERE comment_id = ? AND repo_owner = ? AND repo_name = ? AND pr_number = ?
        """, (456, "owner", "repo", 2))
        
        row = cursor.fetchone()
        assert row is not None
        assert row["comment_id"] == 456
    
    def test_get_last_poll_time(self, storage_db):
        """Test getting last poll time."""
        assert storage_db.get_last_poll_time("owner", "repo", 1) is None
        
        poll_time = datetime(2024, 1, 1, 12, 0, 0)
        storage_db.update_last_poll_time("owner", "repo", 1, poll_time)
        
        retrieved_time = storage_db.get_last_poll_time("owner", "repo", 1)
        assert retrieved_time == poll_time
    
    def test_update_last_poll_time(self, storage_db):
        """Test updating last poll time."""
        poll_time = datetime(2024, 1, 1, 12, 0, 0)
        storage_db.update_last_poll_time("owner", "repo", 1, poll_time)
        
        cursor = storage_db.conn.cursor()
        cursor.execute("""
            SELECT last_polled_at FROM pr_poll_times
            WHERE repo_owner = ? AND repo_name = ? AND pr_number = ?
        """, ("owner", "repo", 1))
        
        row = cursor.fetchone()
        assert row is not None
    
    def test_cleanup_old_processed_comments(self, storage_db):
        """Test cleanup of old processed comments."""
        old_time = datetime.utcnow() - timedelta(days=10)
        recent_time = datetime.utcnow() - timedelta(hours=1)
        
        # Add old comment
        cursor = storage_db.conn.cursor()
        cursor.execute("""
            INSERT INTO processed_comments
            (comment_id, repo_owner, repo_name, pr_number, comment_type, processed_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (1, "owner", "repo", 1, "review_comment", old_time.isoformat()))
        
        # Add recent comment
        cursor.execute("""
            INSERT INTO processed_comments
            (comment_id, repo_owner, repo_name, pr_number, comment_type, processed_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (2, "owner", "repo", 1, "review_comment", recent_time.isoformat()))
        
        storage_db.conn.commit()
        
        # Cleanup comments older than 7 days
        storage_db.cleanup_old_processed_comments(retention_seconds=7 * 24 * 60 * 60)
        
        # Old comment should be gone
        assert storage_db.is_comment_processed(1, "owner", "repo", 1, "review_comment") is False
        # Recent comment should still exist
        assert storage_db.is_comment_processed(2, "owner", "repo", 1, "review_comment") is True
