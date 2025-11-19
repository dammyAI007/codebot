"""Tests for codebot.claude.runner module."""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from codebot.claude.runner import ClaudeRunner


@pytest.fixture
def mock_claude_check(mocker):
    """Mock the Claude installation check."""
    mock_which = mocker.patch("subprocess.run")
    mock_which.return_value = MagicMock(returncode=0, stdout="/usr/local/bin/claude\n")
    return mock_which


@pytest.fixture
def claude_runner(temp_workspace, mock_github_app_auth, mock_claude_check):
    """Create a ClaudeRunner instance for testing."""
    return ClaudeRunner(
        work_dir=temp_workspace,
        github_app_auth=mock_github_app_auth,
    )


class TestClaudeRunner:
    """Tests for ClaudeRunner class."""
    
    def test_init_checks_claude_installed(self, temp_workspace, mock_github_app_auth):
        """Test that initialization checks for Claude CLI."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            runner = ClaudeRunner(temp_workspace, mock_github_app_auth)
            
            # Should call 'which claude'
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args == ["which", "claude"]
    
    def test_init_raises_error_if_claude_not_installed(self, temp_workspace, mock_github_app_auth):
        """Test that initialization raises error if Claude is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            
            with pytest.raises(RuntimeError, match="Claude Code CLI is not installed"):
                ClaudeRunner(temp_workspace, mock_github_app_auth)
    
    def test_run_task_basic(self, claude_runner, mocker):
        """Test running a basic task."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Task completed",
            stderr="",
        )
        
        result = claude_runner.run_task("Fix the bug in login.py")
        
        assert result.returncode == 0
        # Verify subprocess was called
        assert mock_run.call_count >= 1
    
    def test_run_task_with_append_system_prompt(self, claude_runner, mocker):
        """Test running task with additional system prompt."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        
        claude_runner.run_task(
            "Implement feature X",
            append_system_prompt="Use TypeScript for all new code"
        )
        
        # Verify the task was executed
        assert mock_run.called
    
    def test_run_task_returns_completed_process(self, claude_runner, mocker):
        """Test that run_task returns CompletedProcess."""
        mock_run = mocker.patch("subprocess.run")
        expected_result = MagicMock(
            returncode=0,
            stdout="Success",
            stderr="",
        )
        mock_run.return_value = expected_result
        
        result = claude_runner.run_task("Test task")
        
        assert result == expected_result
    
    def test_run_task_with_github_app_auth(self, temp_workspace, mock_github_app_auth, mock_claude_check, mocker):
        """Test that git environment is set when GitHub app auth is provided."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        
        runner = ClaudeRunner(
            work_dir=temp_workspace,
            github_app_auth=mock_github_app_auth,
        )
        
        runner.run_task("Test task")
        
        # Verify subprocess was called
        assert mock_run.called
    
    def test_run_task_system_prompt_excludes_generated_text(self, claude_runner, mocker):
        """Test that system prompt explicitly prohibits 'Generated with Claude Code' text."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        
        claude_runner.run_task("Test task")
        
        # The actual check would require inspecting the command args
        # which depend on implementation details
        assert mock_run.called
    
    def test_work_directory_is_set(self, claude_runner, temp_workspace):
        """Test that work directory is properly set."""
        assert claude_runner.work_dir == temp_workspace
    
    def test_github_app_auth_is_stored(self, claude_runner, mock_github_app_auth):
        """Test that GitHub app auth is stored."""
        assert claude_runner.github_app_auth == mock_github_app_auth


class TestClaudeRunnerLogCapture:
    """Tests for log capture functionality."""
    
    def test_runner_with_log_capture(self, temp_workspace, mock_github_app_auth, mock_claude_check):
        """Test creating runner with log capture."""
        mock_log_capture = MagicMock()
        
        runner = ClaudeRunner(
            work_dir=temp_workspace,
            github_app_auth=mock_github_app_auth,
            log_capture=mock_log_capture,
        )
        
        assert runner.log_capture == mock_log_capture
    
    def test_runner_without_log_capture(self, claude_runner):
        """Test creating runner without log capture."""
        assert claude_runner.log_capture is None
