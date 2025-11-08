"""Unified task storage for CLI and web-initiated tasks."""

import threading
from datetime import datetime
from typing import Dict, List, Optional

from codebot.core.models import Task


class TaskStore:
    """Thread-safe centralized task storage."""
    
    def __init__(self):
        """Initialize task store."""
        self.tasks: Dict[str, Task] = {}
        self.lock = threading.Lock()
    
    def add_task(self, task: Task) -> None:
        """
        Add a task to the store.
        
        Args:
            task: Task to add
        """
        with self.lock:
            self.tasks[task.id] = task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task or None if not found
        """
        with self.lock:
            return self.tasks.get(task_id)
    
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
            task = self.tasks.get(task_id)
            if task:
                if status is not None:
                    task.status = status
                if started_at is not None:
                    task.started_at = started_at
                if completed_at is not None:
                    task.completed_at = completed_at
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
    
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
            source_filter: Filter by source (cli/web)
            limit: Maximum number of tasks to return
            
        Returns:
            List of tasks
        """
        with self.lock:
            tasks = list(self.tasks.values())
        
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        
        if source_filter:
            tasks = [t for t in tasks if t.source == source_filter]
        
        tasks.sort(key=lambda t: t.submitted_at, reverse=True)
        
        return tasks[:limit]
    
    def get_all_tasks(self) -> List[Task]:
        """
        Get all tasks.
        
        Returns:
            List of all tasks
        """
        with self.lock:
            return list(self.tasks.values())
    
    def size(self) -> int:
        """Get total number of tasks."""
        with self.lock:
            return len(self.tasks)


global_task_store = TaskStore()

