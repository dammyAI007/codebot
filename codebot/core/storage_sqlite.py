"""SQLite storage backend for task persistence."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from codebot.core.models import Task, TaskPrompt
from codebot.core.storage import TaskStorage


class SQLiteTaskStorage(TaskStorage):
    """SQLite-based task storage implementation."""
    
    def __init__(self, db_path: Path):
        """
        Initialize SQLite storage.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()
    
    def _create_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error TEXT,
                prompt_json TEXT NOT NULL,
                result_json TEXT,
                subtasks TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source ON tasks(source)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submitted_at ON tasks(submitted_at)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_comments (
                comment_id INTEGER NOT NULL,
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                comment_type TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                PRIMARY KEY (comment_id, repo_owner, repo_name, pr_number, comment_type)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_comments_pr ON processed_comments(repo_owner, repo_name, pr_number)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pr_poll_times (
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                last_polled_at TEXT NOT NULL,
                PRIMARY KEY (repo_owner, repo_name, pr_number)
            )
        """)
        
        self.conn.commit()
    
    def _serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        return dt.isoformat()
    
    def _deserialize_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        if dt_str is None:
            return None
        return datetime.fromisoformat(dt_str)
    
    def _serialize_prompt(self, prompt: TaskPrompt) -> str:
        return json.dumps({
            "repository_url": prompt.repository_url,
            "description": prompt.description,
            "ticket_id": prompt.ticket_id,
            "ticket_summary": prompt.ticket_summary,
            "test_command": prompt.test_command,
            "base_branch": prompt.base_branch,
        })
    
    def _deserialize_prompt(self, prompt_json: str) -> TaskPrompt:
        data = json.loads(prompt_json)
        return TaskPrompt(**data)
    
    def _load_subtasks(self, task_id: str) -> List[Task]:
        """Load subtasks for a given task."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT subtasks FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        
        if not row or not row["subtasks"]:
            return []
        
        subtask_ids = json.loads(row["subtasks"])
        if not subtask_ids:
            return []
        
        subtasks = []
        for subtask_id in subtask_ids:
            subtask = self.get_task(subtask_id)
            if subtask:
                subtasks.append(subtask)
        
        return subtasks
    
    def add_task(self, task: Task) -> None:
        """Add a task to the store."""
        cursor = self.conn.cursor()
        
        subtask_ids = [st.id for st in task.subtasks] if task.subtasks else []
        
        cursor.execute("""
            INSERT OR REPLACE INTO tasks (
                id, status, source, submitted_at, started_at, completed_at,
                error, prompt_json, result_json, subtasks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.id,
            task.status,
            task.source,
            self._serialize_datetime(task.submitted_at),
            self._serialize_datetime(task.started_at),
            self._serialize_datetime(task.completed_at),
            task.error,
            self._serialize_prompt(task.prompt),
            json.dumps(task.result) if task.result else None,
            json.dumps(subtask_ids) if subtask_ids else None,
        ))
        
        self.conn.commit()
        
        for subtask in task.subtasks:
            self.add_task(subtask)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        task = self._row_to_task(row)
        task.subtasks = self._load_subtasks(task_id)
        return task
    
    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """Convert database row to Task object."""
        prompt = self._deserialize_prompt(row["prompt_json"])
        result = json.loads(row["result_json"]) if row["result_json"] else None
        
        return Task(
            id=row["id"],
            prompt=prompt,
            status=row["status"],
            submitted_at=self._deserialize_datetime(row["submitted_at"]),
            source=row["source"],
            started_at=self._deserialize_datetime(row["started_at"]),
            completed_at=self._deserialize_datetime(row["completed_at"]),
            result=result,
            error=row["error"],
            subtasks=[],  # Will be loaded separately
        )
    
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
        """Update task fields."""
        cursor = self.conn.cursor()
        
        updates = []
        values = []
        
        if status is not None:
            updates.append("status = ?")
            values.append(status)
        
        if started_at is not None:
            updates.append("started_at = ?")
            values.append(self._serialize_datetime(started_at))
        
        if completed_at is not None:
            updates.append("completed_at = ?")
            values.append(self._serialize_datetime(completed_at))
        
        if result is not None:
            updates.append("result_json = ?")
            values.append(json.dumps(result))
        
        if error is not None:
            updates.append("error = ?")
            values.append(error)
        
        if subtasks is not None:
            updates.append("subtasks = ?")
            values.append(json.dumps(subtasks) if subtasks else None)
        
        if not updates:
            return
        
        values.append(task_id)
        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        self.conn.commit()
    
    def list_tasks(
        self,
        status_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
        limit: int = 100
    ) -> List[Task]:
        """List tasks with optional filters."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        
        if source_filter:
            query += " AND source = ?"
            params.append(source_filter)
        
        query += " ORDER BY submitted_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        tasks = []
        for row in rows:
            task = self._row_to_task(row)
            task.subtasks = self._load_subtasks(task.id)
            tasks.append(task)
        
        return tasks
    
    def get_all_tasks(self) -> List[Task]:
        """Get all tasks."""
        return self.list_tasks(limit=10000)
    
    def find_task_by_branch_uuid(self, uuid: str) -> Optional[Task]:
        """Find a task by branch UUID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE result_json IS NOT NULL")
        rows = cursor.fetchall()
        
        for row in rows:
            if not row["result_json"]:
                continue
            
            try:
                result = json.loads(row["result_json"])
                branch_name = result.get("branch_name", "")
                if uuid in branch_name:
                    task = self._row_to_task(row)
                    task.subtasks = self._load_subtasks(task.id)
                    return task
            except (json.JSONDecodeError, TypeError):
                continue
        
        return None
    
    def find_task_by_pr_url(self, pr_url: str) -> Optional[Task]:
        """Find a task by PR URL."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE result_json IS NOT NULL")
        rows = cursor.fetchall()
        
        for row in rows:
            if not row["result_json"]:
                continue
            
            try:
                result = json.loads(row["result_json"])
                if result.get("pr_url") == pr_url:
                    task = self._row_to_task(row)
                    task.subtasks = self._load_subtasks(task.id)
                    return task
            except (json.JSONDecodeError, TypeError):
                continue
        
        return None
    
    def close(self) -> None:
        """Close storage connection."""
        self.conn.close()
    
    def is_comment_processed(
        self,
        comment_id: int,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        comment_type: str,
    ) -> bool:
        """Check if a comment has already been processed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 1 FROM processed_comments
            WHERE comment_id = ? AND repo_owner = ? AND repo_name = ? 
            AND pr_number = ? AND comment_type = ?
        """, (comment_id, repo_owner, repo_name, pr_number, comment_type))
        return cursor.fetchone() is not None
    
    def mark_comment_processed(
        self,
        comment_id: int,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        comment_type: str,
    ) -> None:
        """Mark a comment as processed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO processed_comments
            (comment_id, repo_owner, repo_name, pr_number, comment_type, processed_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            comment_id,
            repo_owner,
            repo_name,
            pr_number,
            comment_type,
            self._serialize_datetime(datetime.utcnow()),
        ))
        self.conn.commit()
    
    def get_last_poll_time(
        self,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
    ) -> Optional[datetime]:
        """Get the last poll time for a PR."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT last_polled_at FROM pr_poll_times
            WHERE repo_owner = ? AND repo_name = ? AND pr_number = ?
        """, (repo_owner, repo_name, pr_number))
        row = cursor.fetchone()
        if row:
            return self._deserialize_datetime(row["last_polled_at"])
        return None
    
    def update_last_poll_time(
        self,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        poll_time: datetime,
    ) -> None:
        """Update the last poll time for a PR."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO pr_poll_times
            (repo_owner, repo_name, pr_number, last_polled_at)
            VALUES (?, ?, ?, ?)
        """, (
            repo_owner,
            repo_name,
            pr_number,
            self._serialize_datetime(poll_time),
        ))
        self.conn.commit()
    
    def cleanup_old_processed_comments(self, retention_seconds: int) -> None:
        """Clean up old processed comment records."""
        cutoff_time = datetime.utcnow() - timedelta(seconds=retention_seconds)
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM processed_comments
            WHERE processed_at < ?
        """, (self._serialize_datetime(cutoff_time),))
        self.conn.commit()

