"""Abstract storage interface for task persistence."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from codebot.core.models import Task


class TaskStorage(ABC):
    """Abstract base class for task storage backends."""
    
    @abstractmethod
    def add_task(self, task: Task) -> None:
        """
        Add a task to the store.
        
        Args:
            task: Task to add
        """
        pass
    
    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task or None if not found
        """
        pass
    
    @abstractmethod
    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        result: Optional[dict] = None,
        error: Optional[str] = None,
        subtasks: Optional[List[str]] = None,
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
            subtasks: List of subtask IDs
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def get_all_tasks(self) -> List[Task]:
        """
        Get all tasks.
        
        Returns:
            List of all tasks
        """
        pass
    
    @abstractmethod
    def find_task_by_branch_uuid(self, uuid: str) -> Optional[Task]:
        """
        Find a task by branch UUID.
        
        Args:
            uuid: UUID extracted from branch name
            
        Returns:
            Task or None if not found
        """
        pass
    
    @abstractmethod
    def find_task_by_pr_url(self, pr_url: str) -> Optional[Task]:
        """
        Find a task by PR URL.
        
        Args:
            pr_url: Pull request URL
            
        Returns:
            Task or None if not found
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close storage connection and cleanup resources."""
        pass

