"""REST API endpoints for task submission."""

import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify

from codebot.core.models import Task, TaskPrompt
from codebot.server.auth import require_api_key
from codebot.server.task_queue import TaskQueue


def create_api_blueprint(task_queue: TaskQueue) -> Blueprint:
    """
    Create API blueprint with task endpoints.
    
    Args:
        task_queue: Task queue instance
        
    Returns:
        Flask Blueprint
    """
    api = Blueprint("api", __name__)
    
    @api.route("/tasks/submit", methods=["POST"])
    @require_api_key
    def submit_task():
        """Submit a new task for execution."""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({
                    "error": "Bad Request",
                    "message": "Request body must be JSON"
                }), 400
            
            # Validate required fields
            if "repository_url" not in data:
                return jsonify({
                    "error": "Bad Request",
                    "message": "repository_url is required"
                }), 400
            
            if "description" not in data:
                return jsonify({
                    "error": "Bad Request",
                    "message": "description is required"
                }), 400
            
            # Create TaskPrompt
            try:
                prompt = TaskPrompt(
                    repository_url=data["repository_url"],
                    description=data["description"],
                    ticket_id=data.get("ticket_id"),
                    ticket_summary=data.get("ticket_summary"),
                    test_command=data.get("test_command"),
                    base_branch=data.get("base_branch"),
                )
            except ValueError as e:
                return jsonify({
                    "error": "Bad Request",
                    "message": str(e)
                }), 400
            
            # Generate task ID
            task_id = str(uuid.uuid4())
            
            # Create Task
            task = Task(
                id=task_id,
                prompt=prompt,
                status="pending",
                submitted_at=datetime.utcnow(),
            )
            
            # Enqueue task
            try:
                task_queue.enqueue(task)
            except Exception as e:
                return jsonify({
                    "error": "Internal Server Error",
                    "message": f"Failed to enqueue task: {str(e)}"
                }), 500
            
            return jsonify({
                "task_id": task_id,
                "status": "pending",
                "message": "Task queued successfully"
            }), 202
        
        except Exception as e:
            return jsonify({
                "error": "Internal Server Error",
                "message": str(e)
            }), 500
    
    @api.route("/tasks/<task_id>/status", methods=["GET"])
    @require_api_key
    def get_task_status(task_id: str):
        """Get task status by ID."""
        task = task_queue.get_task(task_id)
        
        if not task:
            return jsonify({
                "error": "Not Found",
                "message": f"Task {task_id} not found"
            }), 404
        
        response = {
            "task_id": task.id,
            "status": task.status,
            "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }
        
        if task.result:
            response["result"] = task.result
        
        if task.error:
            response["error"] = task.error
        
        return jsonify(response), 200
    
    @api.route("/tasks", methods=["GET"])
    @require_api_key
    def list_tasks():
        """List tasks with optional status filter."""
        status_filter = request.args.get("status")
        limit = request.args.get("limit", 100, type=int)
        
        # Validate limit
        if limit < 1 or limit > 1000:
            return jsonify({
                "error": "Bad Request",
                "message": "limit must be between 1 and 1000"
            }), 400
        
        tasks = task_queue.list_tasks(status_filter=status_filter, limit=limit)
        
        return jsonify({
            "tasks": [
                {
                    "task_id": task.id,
                    "status": task.status,
                    "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "repository_url": task.prompt.repository_url,
                    "description": task.prompt.description[:100] + "..." if len(task.prompt.description) > 100 else task.prompt.description,
                }
                for task in tasks
            ],
            "count": len(tasks)
        }), 200
    
    return api

