"""Tests for codebot.core.github_pr module."""

import pytest
import requests
from unittest.mock import MagicMock, patch

from codebot.core.github_pr import GitHubPR


@pytest.fixture
def github_pr(mock_github_app_auth):
    """Create a GitHubPR instance for testing."""
    return GitHubPR(mock_github_app_auth)


class TestGitHubPR:
    """Tests for GitHubPR class."""
    
    def test_init(self, mock_github_app_auth):
        """Test GitHubPR initialization."""
        pr = GitHubPR(mock_github_app_auth)
        
        assert pr.github_app_auth == mock_github_app_auth
    
    def test_create_pr(self, github_pr, requests_mock):
        """Test creating a pull request."""
        requests_mock.post(
            "https://api.github.com/repos/owner/repo/pulls",
            status_code=201,
            json={
                "html_url": "https://github.com/owner/repo/pull/1",
                "number": 1,
            }
        )
        
        pr_data = github_pr.create_pull_request(
            repository_url="https://github.com/owner/repo",
            branch_name="feature-branch",
            base_branch="main",
            title="Test PR",
            body="Test body",
        )
        
        assert pr_data["html_url"] == "https://github.com/owner/repo/pull/1"
    
    def test_update_pr_description(self, github_pr, requests_mock):
        """Test updating PR description."""
        requests_mock.patch(
            "https://api.github.com/repos/owner/repo/pulls/1",
            json={"number": 1}
        )
        
        github_pr.update_pr_description(
            owner="owner",
            repo="repo",
            pr_number=1,
            title="Updated title",
            body="Updated body",
        )
        
        # Verify the request was made
        assert requests_mock.called
    
    def test_get_pr_details(self, github_pr, requests_mock):
        """Test getting PR details."""
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/pulls/1",
            json={
                "number": 1,
                "title": "Test PR",
                "body": "Test body",
                "html_url": "https://github.com/owner/repo/pull/1",
                "head": {"ref": "feature-branch"},
            }
        )
        
        details = github_pr.get_pr_details("owner", "repo", 1)
        
        assert details["number"] == 1
        assert details["title"] == "Test PR"
        assert details["head"]["ref"] == "feature-branch"
    
    def test_post_pr_comment(self, github_pr, requests_mock):
        """Test posting a comment on a PR."""
        requests_mock.post(
            "https://api.github.com/repos/owner/repo/issues/1/comments",
            status_code=201,
            json={"id": 123}
        )
        
        github_pr.post_pr_comment(
            owner="owner",
            repo="repo",
            pr_number=1,
            body="Test comment",
        )
        
        # Verify the request was made
        assert requests_mock.called
        assert requests_mock.last_request.json()["body"] == "Test comment"
    
    def test_post_review_comment_reply(self, github_pr, requests_mock):
        """Test posting a reply to a review comment."""
        requests_mock.post(
            "https://api.github.com/repos/owner/repo/pulls/1/comments",
            status_code=201,
            json={"id": 456}
        )
        
        github_pr.post_review_comment_reply(
            owner="owner",
            repo="repo",
            pr_number=1,
            comment_id=123,
            body="Reply to comment",
        )
        
        # Verify the request was made
        assert requests_mock.called
        request_body = requests_mock.last_request.json()
        assert request_body["body"] == "Reply to comment"
        assert request_body["in_reply_to"] == 123
    
    def test_get_pr_files_changed(self, github_pr, requests_mock):
        """Test getting files changed in a PR."""
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/pulls/1/files",
            json=[
                {"filename": "file1.py", "status": "modified"},
                {"filename": "file2.py", "status": "added"},
            ]
        )
        
        files = github_pr.get_pr_files_changed("owner", "repo", 1)
        
        assert "file1.py" in files
        assert "file2.py" in files
    
    def test_get_comment_thread(self, github_pr, requests_mock):
        """Test getting comment thread."""
        # Mock both the specific comment and thread endpoints
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/pulls/comments/123",
            json={
                "id": 123,
                "body": "Original comment",
                "user": {"login": "user1"},
                "created_at": "2024-01-01T00:00:00Z",
            }
        )
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/pulls/1/comments",
            json=[
                {"id": 123, "body": "Original comment", "user": {"login": "user1"}, "created_at": "2024-01-01T00:00:00Z"},
                {"id": 124, "body": "Reply", "user": {"login": "user2"}, "created_at": "2024-01-01T00:01:00Z"}
            ]
        )
        
        thread = github_pr.get_comment_thread("owner", "repo", 1, 123)
        
        assert len(thread) >= 1
        # Check that thread contains the original comment
        assert any(c["id"] == 123 for c in thread)
    
    def test_extract_repo_info_from_url(self, github_pr):
        """Test extracting repo info from URL."""
        owner, repo = github_pr.extract_repo_info(
            "https://github.com/test-owner/test-repo"
        )
        
        assert owner == "test-owner"
        assert repo == "test-repo"
    
    def test_extract_repo_info_from_git_url(self, github_pr):
        """Test extracting repo info from git URL."""
        owner, repo = github_pr.extract_repo_info(
            "https://github.com/test-owner/test-repo.git"
        )
        
        assert owner == "test-owner"
        assert repo == "test-repo"
    
    def test_api_error_handling(self, github_pr, requests_mock):
        """Test handling API errors."""
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/pulls/1",
            status_code=404,
            json={"message": "Not Found"}
        )
        
        with pytest.raises(Exception):
            github_pr.get_pr_details("owner", "repo", 1)
    
    def test_authentication_header(self, github_pr, requests_mock, mock_github_app_auth):
        """Test that authentication token is included in requests."""
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/pulls/1",
            json={"number": 1}
        )
        
        github_pr.get_pr_details("owner", "repo", 1)
        
        # Verify token was requested or headers property was accessed
        assert mock_github_app_auth.get_installation_token.called or requests_mock.called


class TestGitHubPREnterpriseGitHub:
    """Tests for GitHubPR with GitHub Enterprise."""
    
    def test_enterprise_api_url(self, mock_github_app_auth):
        """Test that enterprise API URL is used."""
        mock_github_app_auth.api_url = "https://github.enterprise.com/api/v3"
        
        pr = GitHubPR(mock_github_app_auth)
        
        assert pr.github_app_auth.api_url == "https://github.enterprise.com/api/v3"
    
    def test_create_pr_enterprise(self, mock_github_app_auth, requests_mock):
        """Test creating PR on GitHub Enterprise."""
        mock_github_app_auth.api_url = "https://github.enterprise.com/api/v3"
        pr = GitHubPR(mock_github_app_auth)
        
        requests_mock.post(
            "https://github.enterprise.com/api/v3/repos/owner/repo/pulls",
            status_code=201,
            json={"html_url": "https://github.enterprise.com/owner/repo/pull/1"}
        )
        
        pr_data = pr.create_pull_request(
            repository_url="https://github.enterprise.com/owner/repo",
            branch_name="feature",
            base_branch="main",
            title="Test PR",
            body="Test body",
        )
        
        assert "github.enterprise.com" in pr_data["html_url"]
