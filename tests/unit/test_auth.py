"""Tests for codebot.server.auth module."""

import base64
import pytest
from flask import Flask, jsonify
from unittest.mock import MagicMock, patch

from codebot.server.auth import require_api_key, require_basic_auth, require_auth


@pytest.fixture
def test_app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    
    @app.route("/api/test")
    @require_api_key
    def api_endpoint():
        return jsonify({"message": "success"})
    
    @app.route("/web/test")
    @require_basic_auth
    def web_endpoint():
        return jsonify({"message": "success"})
    
    @app.route("/hybrid/test")
    @require_auth
    def hybrid_endpoint():
        return jsonify({"message": "success"})
    
    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return test_app.test_client()


class TestRequireAPIKey:
    """Tests for require_api_key decorator."""
    
    def test_valid_api_key_in_bearer_header(self, client):
        """Test authentication with valid API key in Bearer header."""
        with patch("codebot.server.auth.config.is_api_key_valid", return_value=True):
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer test-api-key-123"}
            )
            
            assert response.status_code == 200
            assert response.json["message"] == "success"
    
    def test_valid_api_key_in_x_api_key_header(self, client):
        """Test authentication with valid API key in X-API-Key header."""
        with patch("codebot.server.auth.config.is_api_key_valid", return_value=True):
            response = client.get(
                "/api/test",
                headers={"X-API-Key": "test-api-key-456"}
            )
            
            assert response.status_code == 200
            assert response.json["message"] == "success"
    
    def test_invalid_api_key(self, client):
        """Test authentication with invalid API key."""
        with patch("codebot.server.auth.config.is_api_key_valid", return_value=False):
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer invalid-key"}
            )
            
            assert response.status_code == 401
            assert "Unauthorized" in response.json["error"]
    
    def test_missing_api_key(self, client):
        """Test authentication with missing API key."""
        with patch("codebot.server.auth.config.is_api_key_valid", return_value=False):
            response = client.get("/api/test")
            
            assert response.status_code == 401
            assert "Unauthorized" in response.json["error"]
    
    def test_malformed_bearer_token(self, client):
        """Test authentication with malformed Bearer token."""
        with patch("codebot.server.auth.config.is_api_key_valid", return_value=False):
            response = client.get(
                "/api/test",
                headers={"Authorization": "InvalidFormat test-key"}
            )
            
            assert response.status_code == 401


class TestRequireBasicAuth:
    """Tests for require_basic_auth decorator."""
    
    def test_valid_basic_auth(self, client):
        """Test authentication with valid basic auth credentials."""
        credentials = base64.b64encode(b"admin:password123").decode("utf-8")
        
        with patch("codebot.server.auth.config.has_web_auth", return_value=True):
            with patch("codebot.server.auth.config.is_web_auth_valid", return_value=True):
                response = client.get(
                    "/web/test",
                    headers={"Authorization": f"Basic {credentials}"}
                )
                
                assert response.status_code == 200
                assert response.json["message"] == "success"
    
    def test_invalid_basic_auth(self, client):
        """Test authentication with invalid basic auth credentials."""
        credentials = base64.b64encode(b"admin:wrongpassword").decode("utf-8")
        
        with patch("codebot.server.auth.config.has_web_auth", return_value=True):
            with patch("codebot.server.auth.config.is_web_auth_valid", return_value=False):
                response = client.get(
                    "/web/test",
                    headers={"Authorization": f"Basic {credentials}"}
                )
                
                assert response.status_code == 401
                assert "WWW-Authenticate" in response.headers
    
    def test_missing_basic_auth(self, client):
        """Test authentication with missing basic auth."""
        with patch("codebot.server.auth.config.has_web_auth", return_value=True):
            response = client.get("/web/test")
            
            assert response.status_code == 401
            assert "WWW-Authenticate" in response.headers
    
    def test_no_auth_required_when_not_configured(self, client):
        """Test that no auth is required when web auth is not configured."""
        with patch("codebot.server.auth.config.has_web_auth", return_value=False):
            response = client.get("/web/test")
            
            assert response.status_code == 200
            assert response.json["message"] == "success"
    
    def test_malformed_basic_auth(self, client):
        """Test authentication with malformed basic auth header."""
        with patch("codebot.server.auth.config.has_web_auth", return_value=True):
            response = client.get(
                "/web/test",
                headers={"Authorization": "Basic invalid-base64!!!"}
            )
            
            assert response.status_code == 401


class TestRequireAuth:
    """Tests for require_auth decorator (hybrid authentication)."""
    
    def test_valid_api_key(self, client):
        """Test authentication with valid API key."""
        with patch("codebot.server.auth.config.is_api_key_valid", return_value=True):
            response = client.get(
                "/hybrid/test",
                headers={"Authorization": "Bearer test-api-key"}
            )
            
            assert response.status_code == 200
            assert response.json["message"] == "success"
    
    def test_valid_basic_auth(self, client):
        """Test authentication with valid basic auth."""
        credentials = base64.b64encode(b"admin:password").decode("utf-8")
        
        with patch("codebot.server.auth.config.is_api_key_valid", return_value=False):
            with patch("codebot.server.auth.config.has_web_auth", return_value=True):
                with patch("codebot.server.auth.config.is_web_auth_valid", return_value=True):
                    response = client.get(
                        "/hybrid/test",
                        headers={"Authorization": f"Basic {credentials}"}
                    )
                    
                    assert response.status_code == 200
                    assert response.json["message"] == "success"
    
    def test_api_key_takes_precedence(self, client):
        """Test that API key is checked before basic auth."""
        with patch("codebot.server.auth.config.is_api_key_valid", return_value=True):
            # Even with invalid basic auth, API key should work
            response = client.get(
                "/hybrid/test",
                headers={"Authorization": "Bearer valid-api-key"}
            )
            
            assert response.status_code == 200
    
    def test_no_auth_fails(self, client):
        """Test that request with no auth fails."""
        with patch("codebot.server.auth.config.is_api_key_valid", return_value=False):
            with patch("codebot.server.auth.config.has_web_auth", return_value=False):
                response = client.get("/hybrid/test")
                
                assert response.status_code == 401
