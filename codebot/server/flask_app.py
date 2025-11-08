"""Flask application setup and configuration."""

from pathlib import Path
from typing import Optional

from flask import Flask, jsonify

from codebot.server.task_queue import TaskQueue
from codebot.server.webhook import review_queue


def create_app(task_queue: Optional[TaskQueue] = None) -> Flask:
    """
    Create and configure Flask application.
    
    Args:
        task_queue: Optional task queue for API endpoints
        
    Returns:
        Configured Flask app
    """
    server_dir = Path(__file__).parent
    template_dir = server_dir / "templates"
    static_dir = server_dir / "static"
    
    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir)
    )
    
    # Register webhook handlers
    from codebot.server import webhook
    
    app.add_url_rule(
        "/webhook",
        "handle_webhook",
        webhook.handle_webhook,
        methods=["POST"]
    )
    
    # Register web UI blueprint
    from codebot.server.web_ui import create_web_ui_blueprint
    
    web_ui_bp = create_web_ui_blueprint()
    app.register_blueprint(web_ui_bp)
    print("Web UI registered at /")
    
    # Register API blueprint if task queue is provided
    if task_queue:
        from codebot.server.api import create_api_blueprint
        
        api_bp = create_api_blueprint(task_queue)
        app.register_blueprint(api_bp, url_prefix="/api")
        
        # Store task queue reference for health check
        app.task_queue = task_queue
        print("API endpoints registered at /api")
    
    # Health check endpoint
    @app.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint."""
        response = {
            "status": "healthy",
            "review_queue_size": review_queue.qsize()
        }
        
        # Add task queue size if available
        if hasattr(app, "task_queue"):
            response["task_queue_size"] = app.task_queue.size()
        
        return jsonify(response), 200
    
    return app


def start_server(app: Flask, port: int = 5000, debug: bool = False):
    """
    Start the Flask server.
    
    Args:
        app: Flask application instance
        port: Port to listen on
        debug: Enable debug mode (enables auto-reload and detailed error pages)
    """
    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
        use_reloader=debug,
        reloader_type='stat' if debug else None
    )

