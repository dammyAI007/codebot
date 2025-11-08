"""Server configuration management."""

import os
from typing import List, Optional


class ServerConfig:
    """Server configuration loaded from environment variables."""
    
    def __init__(self):
        """Load configuration from environment."""
        self.api_keys = self._load_api_keys()
        self.max_workers = self._load_max_workers()
        self.task_retention = self._load_task_retention()
        self.max_queue_size = self._load_max_queue_size()
        self.web_username = self._load_web_username()
        self.web_password = self._load_web_password()
    
    def _load_api_keys(self) -> List[str]:
        """Load API keys from environment."""
        keys_str = os.getenv("CODEBOT_API_KEYS", "")
        if not keys_str:
            return []
        return [k.strip() for k in keys_str.split(",") if k.strip()]
    
    def _load_max_workers(self) -> int:
        """Load max workers from environment."""
        try:
            return int(os.getenv("CODEBOT_MAX_WORKERS", "1"))
        except ValueError:
            return 1
    
    def _load_task_retention(self) -> int:
        """Load task retention period in seconds."""
        try:
            return int(os.getenv("CODEBOT_TASK_RETENTION", str(24 * 3600)))
        except ValueError:
            return 24 * 3600
    
    def _load_max_queue_size(self) -> int:
        """Load max queue size from environment."""
        try:
            return int(os.getenv("CODEBOT_MAX_QUEUE_SIZE", "100"))
        except ValueError:
            return 100
    
    def is_api_key_valid(self, api_key: str) -> bool:
        """
        Check if API key is valid.
        
        Args:
            api_key: API key to validate
            
        Returns:
            True if valid, False otherwise
        """
        return api_key in self.api_keys
    
    def has_api_keys(self) -> bool:
        """Check if any API keys are configured."""
        return len(self.api_keys) > 0
    
    def _load_web_username(self) -> Optional[str]:
        """Load web interface username from environment."""
        return os.getenv("CODEBOT_WEB_USERNAME", "admin")
    
    def _load_web_password(self) -> Optional[str]:
        """Load web interface password from environment."""
        return os.getenv("CODEBOT_WEB_PASSWORD")
    
    def has_web_auth(self) -> bool:
        """Check if web authentication is configured."""
        return self.web_password is not None
    
    def is_web_auth_valid(self, username: str, password: str) -> bool:
        """
        Check if web credentials are valid.
        
        Args:
            username: Username to validate
            password: Password to validate
            
        Returns:
            True if valid, False otherwise
        """
        return username == self.web_username and password == self.web_password


# Global config instance
config = ServerConfig()

