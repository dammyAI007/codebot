"""Task queue and status tracking for HTTP-submitted tasks."""

import threading
from datetime import datetime
from queue import Empty, Queue
from typing import Dict, List, Optional

from codebot.core.models import Task


class TaskQueue:
    """Thread-safe task queue with status tracking."""
    
    def __init__(self, max_size: int = 100):
        """
        Initialize task queue.
        
        Args:
            max_size: Maximum number of tasks in queue
        """
        self.queue = Queue(maxsize=max_size)
        self.tasks: Dict[str, Task] = {}
        self.lock = threading.Lock()
    
    def enqueue(self, task: Task) -> None:
        """
        Add a task to the queue.
        
        Args:
            task: Task to enqueue
        """
        with self.lock:
            self.tasks[task.id] = task
        
        self.queue.put(task.id)
    
    def dequeue(self, timeout: float = 1.0) -> Optional[str]:
        """
        Get next task ID from queue.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Task ID or None if queue is empty
        """
        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            return None
    
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
    
    def update_status(
        self,
        task_id: str,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Update task status.
        
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
                task.status = status
                if started_at:
                    task.started_at = started_at
                if completed_at:
                    task.completed_at = completed_at
                if result:
                    task.result = result
                if error:
                    task.error = error
    
    def list_tasks(
        self,
        status_filter: Optional[str] = None,
        limit: int = 100
    ) -> List[Task]:
        """
        List tasks with optional status filter.
        
        Args:
            status_filter: Filter by status
            limit: Maximum number of tasks to return
            
        Returns:
            List of tasks
        """
        with self.lock:
            tasks = list(self.tasks.values())
        
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        
        # Sort by submission time (newest first)
        tasks.sort(key=lambda t: t.submitted_at, reverse=True)
        
        return tasks[:limit]
    
    def size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()
    
    def task_done(self) -> None:
        """Mark task as done in queue."""
        self.queue.task_done()

