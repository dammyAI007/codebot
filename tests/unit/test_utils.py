"""Tests for codebot.core.utils module."""

import os
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from codebot.core.utils import (
    detect_github_info,
    detect_github_api_url,
    is_github_url,
    get_codebot_git_author_info,
    get_git_env,
    generate_short_uuid,
    generate_branch_name,
    generate_directory_name,
    extract_uuid_from_branch,
    find_workspace_by_uuid,
    cleanup_workspace,
)


class TestDetectGitHubInfo:
    """Tests for detect_github_info function."""
    
    def test_detect_github_com(self):
        """Test detecting github.com repository."""
        result = detect_github_info("https://github.com/owner/repo")
        
        assert result["host"] == "github.com"
        assert result["is_enterprise"] == "false"
        assert result["api_url"] == "https://api.github.com"
        assert result["base_url"] == "https://github.com"
    
    def test_detect_enterprise_github(self):
        """Test detecting GitHub Enterprise repository."""
        result = detect_github_info("https://github.enterprise.com/owner/repo")
        
        assert result["host"] == "github.enterprise.com"
        assert result["is_enterprise"] == "true"
        assert result["api_url"] == "https://github.enterprise.com/api/v3"
        assert result["base_url"] == "https://github.enterprise.com"
    
    def test_detect_with_git_suffix(self):
        """Test detecting repository with .git suffix."""
        result = detect_github_info("https://github.com/owner/repo.git")
        
        assert result["host"] == "github.com"
        assert result["is_enterprise"] == "false"
        assert result["api_url"] == "https://api.github.com"
    
    def test_invalid_url_raises_error(self):
        """Test that invalid URL raises ValueError."""
        with pytest.raises(ValueError, match="Invalid repository URL"):
            detect_github_info("not-a-valid-url")


class TestDetectGitHubAPIUrl:
    """Tests for detect_github_api_url function."""
    
    def test_use_github_api_url_env_var(self, monkeypatch):
        """Test using GITHUB_API_URL environment variable."""
        monkeypatch.setenv("GITHUB_API_URL", "https://custom.api.github.com")
        
        result = detect_github_api_url()
        
        assert result == "https://custom.api.github.com"
    
    def test_use_github_enterprise_url_env_var(self, monkeypatch):
        """Test using GITHUB_ENTERPRISE_URL environment variable."""
        monkeypatch.setenv("GITHUB_ENTERPRISE_URL", "https://github.enterprise.com")
        
        result = detect_github_api_url()
        
        assert result == "https://github.enterprise.com/api/v3"
    
    def test_derive_from_repository_url(self):
        """Test deriving API URL from repository URL."""
        result = detect_github_api_url(
            repository_url="https://github.enterprise.com/owner/repo"
        )
        
        assert result == "https://github.enterprise.com/api/v3"
    
    def test_default_to_github_com(self, monkeypatch):
        """Test defaulting to github.com API."""
        monkeypatch.delenv("GITHUB_API_URL", raising=False)
        monkeypatch.delenv("GITHUB_ENTERPRISE_URL", raising=False)
        
        result = detect_github_api_url()
        
        assert result == "https://api.github.com"
    
    def test_strip_trailing_slash(self, monkeypatch):
        """Test that trailing slashes are removed."""
        monkeypatch.setenv("GITHUB_API_URL", "https://api.github.com/")
        
        result = detect_github_api_url()
        
        assert result == "https://api.github.com"


class TestIsGitHubUrl:
    """Tests for is_github_url function."""
    
    def test_github_com_url(self):
        """Test recognizing github.com URL."""
        assert is_github_url("https://github.com/owner/repo") is True
    
    def test_github_enterprise_url(self):
        """Test recognizing GitHub Enterprise URL."""
        assert is_github_url("https://github.enterprise.com/owner/repo") is True
    
    def test_http_github_url(self):
        """Test recognizing HTTP GitHub URL."""
        assert is_github_url("http://github.com/owner/repo") is True
    
    def test_non_github_url(self):
        """Test rejecting non-GitHub URL."""
        assert is_github_url("https://gitlab.com/owner/repo") is False
    
    def test_invalid_url(self):
        """Test handling invalid URL."""
        assert is_github_url("not-a-url") is False
    
    def test_git_protocol_url(self):
        """Test handling git:// protocol (not supported)."""
        assert is_github_url("git://github.com/owner/repo") is False


class TestGetCodebotGitAuthorInfo:
    """Tests for get_codebot_git_author_info function."""
    
    def test_github_com_author_info(self):
        """Test generating author info for github.com."""
        result = get_codebot_git_author_info(
            bot_user_id="123456",
            bot_name="codebot",
            api_url="https://api.github.com"
        )
        
        assert result["author_name"] == "codebot"
        assert result["author_email"] == "123456+codebot@users.noreply.github.com"
        assert result["committer_name"] == "codebot"
        assert result["committer_email"] == "123456+codebot@users.noreply.github.com"
    
    def test_enterprise_author_info(self):
        """Test generating author info for GitHub Enterprise."""
        result = get_codebot_git_author_info(
            bot_user_id="789",
            bot_name="test-bot",
            api_url="https://github.enterprise.com/api/v3"
        )
        
        assert result["author_name"] == "test-bot"
        assert result["author_email"] == "789+test-bot@users.noreply.github.enterprise.com"
    
    def test_missing_bot_name_raises_error(self):
        """Test that missing bot_name raises ValueError."""
        with pytest.raises(ValueError, match="Bot name is required"):
            get_codebot_git_author_info(bot_user_id="123", bot_name=None)
    
    def test_no_api_url_defaults_to_github_com(self):
        """Test that no API URL defaults to github.com email domain."""
        result = get_codebot_git_author_info(
            bot_user_id="456",
            bot_name="my-bot"
        )
        
        assert result["author_email"] == "456+my-bot@users.noreply.github.com"


class TestGetGitEnv:
    """Tests for get_git_env function."""
    
    def test_basic_git_env(self):
        """Test basic git environment variables."""
        env = get_git_env()
        
        assert env["GIT_TERMINAL_PROMPT"] == "0"
        assert env["GIT_ASKPASS"] == "echo"
        assert "PATH" in env  # Should include existing env vars
    
    def test_git_env_with_bot_info(self):
        """Test git environment with bot author information."""
        env = get_git_env(
            bot_user_id="123456",
            bot_name="codebot",
            api_url="https://api.github.com"
        )
        
        assert env["GIT_AUTHOR_NAME"] == "codebot"
        assert env["GIT_AUTHOR_EMAIL"] == "123456+codebot@users.noreply.github.com"
        assert env["GIT_COMMITTER_NAME"] == "codebot"
        assert env["GIT_COMMITTER_EMAIL"] == "123456+codebot@users.noreply.github.com"
    
    def test_git_env_without_bot_info(self):
        """Test git environment without bot information."""
        env = get_git_env()
        
        # get_git_env returns a dict - may or may not have git author info depending on system config
        assert isinstance(env, dict)


class TestGenerateShortUUID:
    """Tests for generate_short_uuid function."""
    
    def test_uuid_length(self):
        """Test that UUID is 7 characters long."""
        uuid = generate_short_uuid()
        assert len(uuid) == 7
    
    def test_uuid_is_hexadecimal(self):
        """Test that UUID contains only hexadecimal characters."""
        uuid = generate_short_uuid()
        assert all(c in "0123456789abcdef" for c in uuid)
    
    def test_uuid_uniqueness(self):
        """Test that consecutive UUIDs are different."""
        uuid1 = generate_short_uuid()
        uuid2 = generate_short_uuid()
        assert uuid1 != uuid2


class TestGenerateBranchName:
    """Tests for generate_branch_name function."""
    
    def test_branch_name_with_all_params(self):
        """Test generating branch name with all parameters."""
        name = generate_branch_name(
            ticket_id="TASK-123",
            short_name="feature",
            uuid_part="abc1234"
        )
        
        assert name == "u/codebot/TASK-123/abc1234/feature"
    
    def test_branch_name_without_ticket_id(self):
        """Test generating branch name without ticket ID."""
        name = generate_branch_name(
            short_name="bugfix",
            uuid_part="def5678"
        )
        
        assert name == "u/codebot/def5678/bugfix"
    
    def test_branch_name_without_short_name(self):
        """Test generating branch name without short name."""
        name = generate_branch_name(
            ticket_id="PROJ-456",
            uuid_part="ghi9012"
        )
        
        assert name == "u/codebot/PROJ-456/ghi9012"
    
    def test_branch_name_minimal(self):
        """Test generating branch name with only UUID."""
        name = generate_branch_name(uuid_part="jkl3456")
        
        assert name == "u/codebot/jkl3456"
    
    def test_branch_name_auto_generates_uuid(self):
        """Test that UUID is auto-generated if not provided."""
        name = generate_branch_name(ticket_id="TASK-789", short_name="test")
        
        parts = name.split("/")
        assert parts[0] == "u"
        assert parts[1] == "codebot"
        assert parts[2] == "TASK-789"
        assert len(parts[3]) == 7  # UUID part
        assert parts[4] == "test"


class TestGenerateDirectoryName:
    """Tests for generate_directory_name function."""
    
    def test_directory_name_with_ticket_id(self):
        """Test generating directory name with ticket ID."""
        name = generate_directory_name(ticket_id="TASK-123", uuid_part="abc1234")
        
        assert name == "task_TASK-123_abc1234"
    
    def test_directory_name_without_ticket_id(self):
        """Test generating directory name without ticket ID."""
        name = generate_directory_name(uuid_part="def5678")
        
        assert name == "task_def5678"
    
    def test_directory_name_auto_generates_uuid(self):
        """Test that UUID is auto-generated if not provided."""
        name = generate_directory_name(ticket_id="PROJ-456")
        
        assert name.startswith("task_PROJ-456_")
        uuid_part = name.split("_")[-1]
        assert len(uuid_part) == 7


class TestExtractUUIDFromBranch:
    """Tests for extract_uuid_from_branch function."""
    
    def test_extract_uuid_full_branch(self):
        """Test extracting UUID from full branch name."""
        uuid = extract_uuid_from_branch("u/codebot/TASK-123/abc1234/feature")
        
        assert uuid == "abc1234"
    
    def test_extract_uuid_no_ticket_id(self):
        """Test extracting UUID from branch without ticket ID."""
        uuid = extract_uuid_from_branch("u/codebot/def5678/bugfix")
        
        assert uuid == "def5678"
    
    def test_extract_uuid_invalid_branch(self):
        """Test that invalid branch returns None."""
        uuid = extract_uuid_from_branch("feature/my-feature")
        
        assert uuid is None
    
    def test_extract_uuid_wrong_prefix(self):
        """Test that branch with wrong prefix returns None."""
        uuid = extract_uuid_from_branch("feature/codebot/abc1234")
        
        assert uuid is None
    
    def test_extract_uuid_non_hex_string(self):
        """Test that non-hexadecimal UUID returns None."""
        uuid = extract_uuid_from_branch("u/codebot/TASK-123")
        
        assert uuid is None


class TestFindWorkspaceByUUID:
    """Tests for find_workspace_by_uuid function."""
    
    def test_find_workspace_with_ticket_id(self, tmp_path):
        """Test finding workspace with ticket ID in name."""
        workspace = tmp_path / "task_TASK-123_abc1234"
        workspace.mkdir()
        
        result = find_workspace_by_uuid(tmp_path, "abc1234")
        
        assert result == workspace
    
    def test_find_workspace_without_ticket_id(self, tmp_path):
        """Test finding workspace without ticket ID."""
        workspace = tmp_path / "task_def5678"
        workspace.mkdir()
        
        result = find_workspace_by_uuid(tmp_path, "def5678")
        
        assert result == workspace
    
    def test_find_workspace_nonexistent(self, tmp_path):
        """Test that nonexistent workspace returns None."""
        result = find_workspace_by_uuid(tmp_path, "xyz9999")
        
        assert result is None
    
    def test_find_workspace_nonexistent_base_dir(self):
        """Test that nonexistent base directory returns None."""
        result = find_workspace_by_uuid(Path("/nonexistent"), "abc1234")
        
        assert result is None
    
    def test_find_workspace_multiple_workspaces(self, tmp_path):
        """Test finding specific workspace among multiple."""
        workspace1 = tmp_path / "task_abc1111"
        workspace2 = tmp_path / "task_TASK-456_abc2222"
        workspace3 = tmp_path / "task_abc3333"
        
        workspace1.mkdir()
        workspace2.mkdir()
        workspace3.mkdir()
        
        result = find_workspace_by_uuid(tmp_path, "abc2222")
        
        assert result == workspace2


class TestCleanupWorkspace:
    """Tests for cleanup_workspace function."""
    
    def test_cleanup_existing_workspace(self, tmp_path):
        """Test cleaning up existing workspace."""
        workspace = tmp_path / "test_workspace"
        workspace.mkdir()
        (workspace / "file.txt").write_text("test")
        
        result = cleanup_workspace(workspace)
        
        assert result is True
        assert not workspace.exists()
    
    def test_cleanup_nonexistent_workspace(self, tmp_path):
        """Test cleaning up nonexistent workspace."""
        workspace = tmp_path / "nonexistent"
        
        result = cleanup_workspace(workspace)
        
        assert result is False
    
    def test_cleanup_file_instead_of_directory(self, tmp_path):
        """Test that cleaning up a file (not directory) returns False."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")
        
        result = cleanup_workspace(file_path)
        
        assert result is False
    
    def test_cleanup_workspace_with_subdirectories(self, tmp_path):
        """Test cleaning up workspace with nested directories."""
        workspace = tmp_path / "test_workspace"
        workspace.mkdir()
        subdir = workspace / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("test")
        
        result = cleanup_workspace(workspace)
        
        assert result is True
        assert not workspace.exists()
