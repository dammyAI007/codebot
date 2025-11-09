"""Unified task storage for CLI and web-initiated tasks."""

import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from codebot.core.models import Task
from codebot.core.storage import TaskStorage
from codebot.core.storage_sqlite import SQLiteTaskStorage


def _get_data_dir(workspace_base_dir: Optional[Path] = None) -> Path:
    """
    Determine the data directory path.
    
    Args:
        workspace_base_dir: Optional workspace base directory.
                           If provided, data dir will be sibling to it.
                           Otherwise, defaults to ./codebot_data
        
    Returns:
        Path to data directory
    """
    if workspace_base_dir:
        return workspace_base_dir.parent / "codebot_data"
    return Path.cwd() / "codebot_data"


def _create_storage(workspace_base_dir: Optional[Path] = None) -> TaskStorage:
    """
    Create storage instance.
    
    Args:
        workspace_base_dir: Optional workspace base directory
        
    Returns:
        TaskStorage instance
    """
    data_dir = _get_data_dir(workspace_base_dir)
    db_path = data_dir / "tasks.db"
    return SQLiteTaskStorage(db_path)


class TaskStore:
    """Thread-safe centralized task storage wrapper."""
    
    def __init__(self, storage: Optional[TaskStorage] = None):
        """
        Initialize task store.
        
        Args:
            storage: Optional storage backend. If not provided, creates SQLite storage.
        """
        self.storage = storage or _create_storage()
        self.lock = threading.Lock()
    
    def add_task(self, task: Task) -> None:
        """
        Add a task to the store.
        
        Args:
            task: Task to add
        """
        with self.lock:
            self.storage.add_task(task)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task or None if not found
        """
        with self.lock:
            return self.storage.get_task(task_id)
    
    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Update task fields.
        
        Args:
            task_id: Task ID
            status: New status
            started_at: When task started
            completed_at: When task completed
            result: Task result
            error: Error message if failed
        """
        with self.lock:
            self.storage.update_task(
                task_id=task_id,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                result=result,
                error=error,
            )
    
    def list_tasks(
        self,
        status_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
        limit: int = 100
    ) -> List[Task]:
        """
        List tasks with optional filters.
        
        Args:
            status_filter: Filter by status
            source_filter: Filter by source (cli/web/review)
            limit: Maximum number of tasks to return
            
        Returns:
            List of tasks
        """
        with self.lock:
            return self.storage.list_tasks(
                status_filter=status_filter,
                source_filter=source_filter,
                limit=limit
            )
    
    def get_all_tasks(self) -> List[Task]:
        """
        Get all tasks.
        
        Returns:
            List of all tasks
        """
        with self.lock:
            return self.storage.get_all_tasks()
    
    def find_task_by_branch_uuid(self, uuid: str) -> Optional[Task]:
        """
        Find a task by branch UUID.
        
        Args:
            uuid: UUID extracted from branch name
            
        Returns:
            Task or None if not found
        """
        with self.lock:
            return self.storage.find_task_by_branch_uuid(uuid)
    
    def find_task_by_pr_url(self, pr_url: str) -> Optional[Task]:
        """
        Find a task by PR URL.
        
        Args:
            pr_url: Pull request URL
            
        Returns:
            Task or None if not found
        """
        with self.lock:
            return self.storage.find_task_by_pr_url(pr_url)
    
    def size(self) -> int:
        """Get total number of tasks."""
        with self.lock:
            return len(self.storage.get_all_tasks())
    
    def close(self) -> None:
        """Close storage connection."""
        with self.lock:
            self.storage.close()


global_task_store = TaskStore()

