"""Data models for codebot."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TaskPrompt:
    """Task prompt model."""
    
    repository_url: str
    description: str
    ticket_id: Optional[str] = None
    ticket_summary: Optional[str] = None
    test_command: Optional[str] = None
    base_branch: Optional[str] = None
    
    def __post_init__(self):
        """Validate required fields."""
        if not self.repository_url:
            raise ValueError("repository_url is required")
        if not self.description:
            raise ValueError("description is required")


@dataclass
class Task:
    """Task execution tracking model."""
    
    id: str
    prompt: TaskPrompt
    status: str
    submitted_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None
