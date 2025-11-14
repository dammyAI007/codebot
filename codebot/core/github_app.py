"""GitHub App authentication using JWT and installation tokens."""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import jwt
import requests
from dotenv import load_dotenv

from codebot.core.utils import detect_github_api_url


class GitHubAppAuth:
    """Handle GitHub App authentication using JWT and installation tokens."""
    
    def __init__(
        self,
        app_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        installation_id: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        """
        Initialize GitHub App authentication.
        
        Args:
            app_id: GitHub App ID (defaults to GITHUB_APP_ID env var)
            private_key_path: Path to private key file (defaults to GITHUB_APP_PRIVATE_KEY_PATH env var)
            installation_id: Installation ID (defaults to GITHUB_APP_INSTALLATION_ID env var)
            api_url: GitHub API URL (auto-detected if not provided)
        """
        load_dotenv()
        
        app_id_env = os.getenv("GITHUB_APP_ID")
        private_key_path_env = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH")
        installation_id_env = os.getenv("GITHUB_APP_INSTALLATION_ID")
        
        self.app_id = app_id or app_id_env
        self.private_key_path = private_key_path or private_key_path_env
        self.installation_id = installation_id or installation_id_env
        
        if not self.app_id:
            raise RuntimeError(
                "GitHub App ID not found. Please set GITHUB_APP_ID environment variable or add it to a .env file."
            )
        
        if not self.private_key_path:
            raise RuntimeError(
                "GitHub App private key path not found. Please set GITHUB_APP_PRIVATE_KEY_PATH environment variable or add it to a .env file."
            )
        
        if not self.installation_id:
            raise RuntimeError(
                "GitHub App installation ID not found. Please set GITHUB_APP_INSTALLATION_ID environment variable or add it to a .env file."
            )
        
        original_path = Path(self.private_key_path)
        key_path = None
        
        if original_path.is_absolute():
            key_path = original_path.resolve()
            if key_path.exists():
                pass
            else:
                key_path = None
        
        if not key_path or not key_path.exists():
            key_path = (Path.cwd() / original_path).resolve()
            if not key_path.exists():
                key_path = None
        
        if not key_path or not key_path.exists():
            filename_only = original_path.name
            key_path = (Path.cwd() / filename_only).resolve()
        
        if not key_path.exists():
            cwd_files = [f.name for f in Path.cwd().iterdir() if f.is_file() and f.name.endswith('.pem')]
            raise RuntimeError(
                f"GitHub App private key file not found.\n"
                f"  Tried: {original_path.resolve()}\n"
                f"  Tried: {(Path.cwd() / original_path).resolve()}\n"
                f"  Tried: {(Path.cwd() / original_path.name).resolve()}\n"
                f"  Original path from env: {self.private_key_path}\n"
                f"  Current working directory: {Path.cwd()}\n"
                f"  PEM files found in directory: {cwd_files}"
            )
        
        if not key_path.is_file():
            raise RuntimeError(f"GitHub App private key path is not a file: {key_path}")
        
        self.private_key_path_resolved = key_path
        
        try:
            self.private_key = key_path.read_text()
        except Exception as e:
            raise RuntimeError(f"Failed to read GitHub App private key file {key_path}: {e}")
        
        self.api_url = api_url or detect_github_api_url()
        
        self.bot_name = os.getenv("GITHUB_BOT_NAME")
        if not self.bot_name:
            raise RuntimeError(
                "GitHub Bot name not found. Please set GITHUB_BOT_NAME environment variable or add it to a .env file."
            )
        
        self._installation_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._bot_user_id: Optional[str] = None
    
    def get_installation_token(self) -> str:
        """
        Get installation access token, using cache if still valid.
        
        Returns:
            Installation access token
        """
        if self._installation_token and time.time() < (self._token_expires_at - 300):
            return self._installation_token
        
        jwt_token = self._generate_jwt()
        
        url = f"{self.api_url}/app/installations/{self.installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        
        response = requests.post(url, headers=headers, timeout=10)
        
        if response.status_code != 201:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get("message", "Unknown error")
            raise RuntimeError(
                f"Failed to get installation access token: {error_msg}\n"
                f"Status code: {response.status_code}\n"
                f"Response: {error_data}"
            )
        
        token_data = response.json()
        self._installation_token = token_data["token"]
        
        expires_at_str = token_data.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            self._token_expires_at = expires_at.timestamp()
        else:
            self._token_expires_at = time.time() + 3600
        
        return self._installation_token
    
    def _generate_jwt(self) -> str:
        """
        Generate JWT for GitHub App authentication.
        
        Returns:
            JWT token string
        """
        now = int(time.time())
        
        payload = {
            "iat": now - 60,  # Issued at time (1 minute ago to account for clock skew)
            "exp": now + (10 * 60),  # Expires in 10 minutes
            "iss": self.app_id,  # Issuer (GitHub App ID)
        }
        
        try:
            token = jwt.encode(payload, self.private_key, algorithm="RS256")
            return token
        except Exception as e:
            raise RuntimeError(f"Failed to generate JWT: {e}")
    
    def get_auth_headers(self) -> dict:
        """
        Get authentication headers for GitHub API requests.
        
        Returns:
            Dictionary with Authorization header
        """
        token = self.get_installation_token()
        return {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
    
    def get_bot_user_id(self) -> str:
        """
        Get the GitHub App bot user ID.
        
        The bot user ID is different from the App ID. It's the user ID of the
        bot account that GitHub creates for the app (e.g., codebot-007[bot]).
        
        Returns:
            Bot user ID as string
            
        Raises:
            RuntimeError: If unable to retrieve bot user ID
        """
        if self._bot_user_id:
            return self._bot_user_id
        
        token = self.get_installation_token()
        
        url = f"{self.api_url}/users/{self.bot_name}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("message", "Unknown error")
                raise RuntimeError(
                    f"Failed to get bot user ID: {error_msg}\n"
                    f"Status code: {response.status_code}\n"
                    f"Response: {error_data}"
                )
            
            user_data = response.json()
            bot_user_id = str(user_data.get("id"))
            
            if not bot_user_id:
                raise RuntimeError("Bot user ID not found in API response")
            
            self._bot_user_id = bot_user_id
            return bot_user_id
            
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to retrieve bot user ID: {e}")
    
    @property
    def bot_user_id(self) -> Optional[str]:
        """
        Get the GitHub App bot user ID (cached property).

        Returns:
            Bot user ID as string, or None if retrieval fails
        """
        if self._bot_user_id:
            return self._bot_user_id

        try:
            return self.get_bot_user_id()
        except Exception as e:
            print(f"Warning: Could not retrieve bot user ID: {e}")
            return None

    def get_bot_login(self) -> str:
        """
        Get the GitHub App bot user login name.

        The bot login follows the format: {app_name}[bot]
        Retrieved from GITHUB_BOT_NAME environment variable.

        Returns:
            Bot login name as string
        """
        return self.bot_name

