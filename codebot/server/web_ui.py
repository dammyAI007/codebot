"""Web UI routes for task management."""

import uuid
from datetime import datetime

from flask import Blueprint, render_template, jsonify, request, current_app

from codebot.core.models import Task
from codebot.core.task_store import global_task_store
from codebot.server.auth import require_basic_auth


def create_web_ui_blueprint() -> Blueprint:
    """
    Create web UI blueprint with task management routes.
    
    Returns:
        Flask Blueprint
    """
    web_ui = Blueprint("web_ui", __name__)
    
    @web_ui.route("/", methods=["GET"])
    @require_basic_auth
    def index():
        """Serve main tasks page."""
        return render_template("tasks.html")
    
    @web_ui.route("/api/web/tasks", methods=["GET"])
    @require_basic_auth
    def list_tasks():
        """List tasks with optional filtering."""
        status_filter = request.args.get("status")
        source_filter = request.args.get("source")
        limit = request.args.get("limit", 50, type=int)
        
        if limit < 1 or limit > 1000:
            return jsonify({
                "error": "Bad Request",
                "message": "limit must be between 1 and 1000"
            }), 400
        
        tasks = global_task_store.list_tasks(
            status_filter=status_filter,
            source_filter=source_filter,
            limit=limit
        )
        
        tasks = [t for t in tasks if t.source != "review"]
        
        def serialize_task(task: Task) -> dict:
            return {
                "id": task.id,
                "source": task.source,
                "status": task.status,
                "repository_url": task.prompt.repository_url,
                "description": task.prompt.description,
                "ticket_id": task.prompt.ticket_id,
                "ticket_summary": task.prompt.ticket_summary,
                "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "result": task.result,
                "error": task.error,
                "subtasks": [serialize_task(st) for st in task.subtasks] if task.subtasks else [],
            }
        
        return jsonify({
            "tasks": [serialize_task(task) for task in tasks],
            "count": len(tasks)
        }), 200
    
    @web_ui.route("/api/web/tasks/<task_id>", methods=["GET"])
    @require_basic_auth
    def get_task(task_id: str):
        """Get task details by ID."""
        task = global_task_store.get_task(task_id)
        
        if not task:
            return jsonify({
                "error": "Not Found",
                "message": f"Task {task_id} not found"
            }), 404
        
        def serialize_task(task: Task) -> dict:
            return {
                "id": task.id,
                "source": task.source,
                "status": task.status,
                "repository_url": task.prompt.repository_url,
                "description": task.prompt.description,
                "ticket_id": task.prompt.ticket_id,
                "ticket_summary": task.prompt.ticket_summary,
                "test_command": task.prompt.test_command,
                "base_branch": task.prompt.base_branch,
                "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "result": task.result,
                "error": task.error,
                "subtasks": [serialize_task(st) for st in task.subtasks] if task.subtasks else [],
            }
        
        return jsonify(serialize_task(task)), 200
    
    @web_ui.route("/api/web/tasks/<task_id>/retry", methods=["POST"])
    @require_basic_auth
    def retry_task(task_id: str):
        """Retry a failed task by creating a new task with the same prompt."""
        original_task = global_task_store.get_task(task_id)
        
        if not original_task:
            return jsonify({
                "error": "Not Found",
                "message": f"Task {task_id} not found"
            }), 404
        
        if original_task.status != "failed":
            return jsonify({
                "error": "Bad Request",
                "message": f"Task {task_id} is not in failed status. Only failed tasks can be retried."
            }), 400
        
        if original_task.source != "web":
            return jsonify({
                "error": "Bad Request",
                "message": "Only web-initiated tasks can be retried through the web interface."
            }), 400
        
        task_queue = getattr(current_app, "task_queue", None)
        if not task_queue:
            return jsonify({
                "error": "Service Unavailable",
                "message": "Task queue is not available. API may not be enabled."
            }), 503
        
        new_task_id = str(uuid.uuid4())
        new_task = Task(
            id=new_task_id,
            prompt=original_task.prompt,
            status="pending",
            submitted_at=datetime.utcnow(),
            source="web",
        )
        
        try:
            task_queue.enqueue(new_task)
        except Exception as e:
            return jsonify({
                "error": "Internal Server Error",
                "message": f"Failed to enqueue retry task: {str(e)}"
            }), 500
        
        return jsonify({
            "task_id": new_task_id,
            "original_task_id": task_id,
            "status": "pending",
            "message": "Task retry queued successfully"
        }), 202
    
    return web_ui

