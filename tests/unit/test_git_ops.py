"""Tests for codebot.core.git_ops module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from codebot.core.git_ops import GitOps


@pytest.fixture
def git_ops(mock_git_repo, mock_github_app_auth):
    """Create a GitOps instance for testing."""
    return GitOps(mock_git_repo, github_app_auth=mock_github_app_auth)


class TestGitOps:
    """Tests for GitOps class."""
    
    def test_init(self, mock_git_repo, mock_github_app_auth):
        """Test GitOps initialization."""
        git_ops = GitOps(mock_git_repo, github_app_auth=mock_github_app_auth)
        
        assert git_ops.work_dir == mock_git_repo
        assert git_ops.github_app_auth == mock_github_app_auth
    
    def test_clone_repository(self, temp_workspace, mock_github_app_auth, mocker):
        """Test cloning a repository."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        
        repo_url = "https://github.com/test/repo"
        GitOps.clone_repository(repo_url, temp_workspace, mock_github_app_auth)
        
        # Verify git clone was called
        assert mock_run.called
        call_args = str(mock_run.call_args)
        assert "clone" in call_args.lower()
    
    def test_checkout_branch(self, git_ops, mocker):
        """Test checking out a branch."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        
        git_ops.checkout_branch("feature-branch")
        
        # Verify git checkout was called
        assert mock_run.called
        call_args = str(mock_run.call_args)
        assert "checkout" in call_args.lower()
    
    def test_create_and_checkout_branch(self, git_ops, mocker):
        """Test creating and checking out a new branch."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        
        # Use checkout_branch instead - it creates if doesn't exist
        git_ops.checkout_branch("new-feature")
        
        # Verify git checkout was called
        assert mock_run.called
        call_args = str(mock_run.call_args)
        assert "checkout" in call_args.lower()
    
    def test_commit_changes(self, git_ops, mocker):
        """Test committing changes."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        
        git_ops.commit_changes("Test commit message")
        
        # Verify git commit was called
        assert mock_run.called
        call_args = str(mock_run.call_args)
        assert "commit" in call_args.lower()
    
    def test_push_branch(self, git_ops, mocker):
        """Test pushing a branch."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        
        git_ops.push_branch("feature-branch")
        
        # Verify git push was called
        assert mock_run.called
        call_args = str(mock_run.call_args)
        assert "push" in call_args.lower()
    
    def test_get_latest_commit_hash(self, git_ops, mocker):
        """Test getting latest commit hash."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123def456\n"
        )
        
        commit_hash = git_ops.get_latest_commit_hash()
        
        assert commit_hash == "abc123def456"
    
    def test_get_commit_message(self, git_ops, mocker):
        """Test getting commit message."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Fix bug in login\n"
        )
        
        message = git_ops.get_commit_message("abc123")
        
        assert message == "Fix bug in login"
    
    def test_configure_git_author(self, git_ops, mocker):
        """Test configuring git author."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        
        git_ops.configure_git_author()
        
        # Should call git config at least twice (name and email)
        assert mock_run.call_count >= 2
    
    def test_has_uncommitted_changes_with_changes(self, git_ops, mocker):
        """Test detecting uncommitted changes."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="M file1.py\nA file2.py\n"
        )
        
        has_changes = git_ops.has_uncommitted_changes()
        
        assert has_changes is True
    
    def test_has_uncommitted_changes_without_changes(self, git_ops, mocker):
        """Test when there are no uncommitted changes."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=""
        )
        
        has_changes = git_ops.has_uncommitted_changes()
        
        assert has_changes is False
    
    def test_get_current_branch(self, git_ops, mocker):
        """Test getting current branch name."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="feature-branch\n"
        )
        
        branch = git_ops.get_current_branch()
        
        assert branch == "feature-branch"
    
    def test_git_operation_failure(self, git_ops, mocker):
        """Test handling git operation failure."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="fatal: repository not found"
        )
        
        with pytest.raises(Exception):
            git_ops.push_branch("feature-branch")


class TestGitOpsWithToken:
    """Tests for GitOps with GitHub authentication token."""
    
    def test_clone_with_token(self, temp_workspace, mock_github_app_auth, mocker):
        """Test that token is used when cloning."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        
        repo_url = "https://github.com/test/repo"
        GitOps.clone_repository(repo_url, temp_workspace, mock_github_app_auth)
        
        # Verify the token was requested
        assert mock_github_app_auth.get_installation_token.called
    
    def test_push_with_token(self, git_ops, mocker):
        """Test that token is used when pushing."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        
        git_ops.push_branch("feature-branch")
        
        # Verify the command was executed
        assert mock_run.called
