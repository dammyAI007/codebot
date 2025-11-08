"""Task processor for HTTP-submitted tasks."""

import threading
from datetime import datetime
from pathlib import Path
from queue import Empty
from typing import Optional

from codebot.core.github_app import GitHubAppAuth
from codebot.core.orchestrator import Orchestrator
from codebot.server.task_queue import TaskQueue


class TaskProcessor:
    """Process tasks from the task queue."""
    
    def __init__(
        self,
        task_queue: TaskQueue,
        workspace_base_dir: Path,
        github_app_auth: GitHubAppAuth,
        num_workers: int = 1,
    ):
        """
        Initialize task processor.
        
        Args:
            task_queue: Task queue instance
            workspace_base_dir: Base directory for workspaces
            github_app_auth: GitHub App authentication instance
            num_workers: Number of worker threads
        """
        self.task_queue = task_queue
        self.workspace_base_dir = workspace_base_dir
        self.github_app_auth = github_app_auth
        self.num_workers = num_workers
        self.running = False
        self.workers = []
    
    def start(self):
        """Start worker threads."""
        self.running = True
        print(f"Starting {self.num_workers} task processor worker(s)...")
        
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker,
                name=f"TaskWorker-{i+1}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
    
    def stop(self):
        """Stop worker threads."""
        self.running = False
        print("Stopping task processor...")
    
    def _worker(self):
        """Worker thread that processes tasks from queue."""
        worker_name = threading.current_thread().name
        print(f"{worker_name} started")
        
        while self.running:
            try:
                task_id = self.task_queue.dequeue(timeout=1.0)
                
                if not task_id:
                    continue
                
                task = self.task_queue.get_task(task_id)
                
                if not task:
                    print(f"{worker_name}: Task {task_id} not found")
                    self.task_queue.task_done()
                    continue
                
                print(f"\n{'=' * 80}")
                print(f"{worker_name}: Processing task {task_id}")
                print(f"{'=' * 80}\n")
                
                self.process_task(task_id)
                
            except Exception as e:
                print(f"{worker_name}: Error in worker loop: {e}")
            finally:
                if task_id:
                    self.task_queue.task_done()
        
        print(f"{worker_name} stopped")
    
    def process_task(self, task_id: str):
        """
        Process a single task.
        
        Args:
            task_id: Task ID to process
        """
        task = self.task_queue.get_task(task_id)
        
        if not task:
            print(f"ERROR: Task {task_id} not found")
            return
        
        # Update status to running
        self.task_queue.update_status(
            task_id,
            status="running",
            started_at=datetime.utcnow()
        )
        
        try:
            # Create orchestrator
            orchestrator = Orchestrator(
                task=task.prompt,
                work_base_dir=self.workspace_base_dir,
                github_app_auth=self.github_app_auth,
            )
            
            # Run task
            print(f"Executing task {task_id}...")
            orchestrator.run()
            
            # Get result
            result = {
                "pr_url": orchestrator.pr_url,
                "branch_name": orchestrator.branch_name,
                "work_dir": str(orchestrator.work_dir) if orchestrator.work_dir else None,
            }
            
            # Update status to completed
            self.task_queue.update_status(
                task_id,
                status="completed",
                completed_at=datetime.utcnow(),
                result=result
            )
            
            print(f"Task {task_id} completed successfully")
            
        except Exception as e:
            print(f"ERROR: Task {task_id} failed: {e}")
            
            # Update status to failed
            self.task_queue.update_status(
                task_id,
                status="failed",
                completed_at=datetime.utcnow(),
                error=str(e)
            )

