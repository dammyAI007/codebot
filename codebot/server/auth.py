"""API authentication for HTTP endpoints."""

from functools import wraps
from flask import request, jsonify

from codebot.server.config import config


def require_api_key(f):
    """
    Decorator to require API key authentication.
    
    Checks for API key in:
    - Authorization: Bearer <api_key> header
    - X-API-Key: <api_key> header
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = None
        
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        
        # Check X-API-Key header
        if not api_key:
            api_key = request.headers.get("X-API-Key")
        
        # Validate API key
        if not api_key or not config.is_api_key_valid(api_key):
            return jsonify({
                "error": "Unauthorized",
                "message": "Invalid or missing API key"
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

