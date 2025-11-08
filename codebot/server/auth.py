"""API authentication for HTTP endpoints."""

import base64
from functools import wraps
from flask import request, jsonify, Response

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


def require_basic_auth(f):
    """
    Decorator to require HTTP Basic Authentication for web interface.
    
    Validates credentials against CODEBOT_WEB_USERNAME and CODEBOT_WEB_PASSWORD.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not config.has_web_auth():
            return f(*args, **kwargs)
        
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Basic "):
            return _make_auth_response()
        
        try:
            encoded = auth_header[6:]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)
            
            if not config.is_web_auth_valid(username, password):
                return _make_auth_response()
        except Exception:
            return _make_auth_response()
        
        return f(*args, **kwargs)
    
    return decorated_function


def _make_auth_response() -> Response:
    """Create HTTP 401 response with Basic Auth challenge."""
    response = Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Codebot Web Interface"'}
    )
    return response

