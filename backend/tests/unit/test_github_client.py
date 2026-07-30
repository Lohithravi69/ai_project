from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from backend.github.client import GitHubClient


@pytest.fixture
def mock_github():
    with patch("backend.github.client.Github") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.id = 12345
    repo.full_name = "testuser/test-repo"
    repo.clone_url = "https://github.com/testuser/test-repo.git"
    repo.default_branch = "main"
    repo.description = "A test repository"
    repo.language = "Python"
    repo.stargazers_count = 42
    repo.forks_count = 7
    repo.private = False
    repo.archived = False
    type(repo).updated_at = PropertyMock(return_value=__import__("datetime").datetime(2025, 1, 15, 12, 0, 0))
    return repo


class TestGitHubClientInit:
    def test_with_token(self):
        client = GitHubClient("ghp_fake_token")
        assert client.token == "ghp_fake_token"

    def test_with_empty_token(self):
        client = GitHubClient("")
        assert client.token == ""


class TestGitHubClientGetUserLogin:
    def test_returns_login(self, mock_github):
        mock_github.get_user.return_value.login = "testuser"
        client = GitHubClient("fake_token")
        assert client.get_user_login() == "testuser"
        mock_github.get_user.assert_called_once()


class TestGitHubClientListRepositories:
    def test_returns_repo_info_list(self, mock_github, mock_repo):
        mock_github.get_user.return_value.get_repos.return_value = [mock_repo]
        client = GitHubClient("fake_token")
        repos = client.list_repositories()
        assert len(repos) == 1
        repo = repos[0]
        assert repo.github_id == 12345
        assert repo.full_name == "testuser/test-repo"
        assert repo.clone_url == "https://github.com/testuser/test-repo.git"
        assert repo.default_branch == "main"
        assert repo.description == "A test repository"
        assert repo.language == "Python"
        assert repo.stars == 42
        assert repo.forks == 7
        assert repo.metadata["private"] is False
        assert repo.metadata["archived"] is False
        mock_github.get_user.return_value.get_repos.assert_called_once()

    def test_empty_repos(self, mock_github):
        mock_github.get_user.return_value.get_repos.return_value = []
        client = GitHubClient("fake_token")
        repos = client.list_repositories()
        assert repos == []

    def test_default_branch_fallback(self, mock_github):
        repo = MagicMock()
        repo.default_branch = None
        repo.full_name = "user/repo"
        repo.clone_url = "https://github.com/user/repo.git"
        repo.description = None
        repo.language = None
        repo.stargazers_count = 0
        repo.forks_count = 0
        repo.private = False
        repo.archived = False
        repo.id = 1
        type(repo).updated_at = PropertyMock(return_value=__import__("datetime").datetime(2025, 1, 1, 0, 0, 0))
        mock_github.get_user.return_value.get_repos.return_value = [repo]
        client = GitHubClient("fake_token")
        repos = client.list_repositories()
        assert repos[0].default_branch == "main"


class TestGitHubClientCloneOrPull:
    def test_clone_new_repository(self, tmp_path: Path, mock_github):
        local_path = tmp_path / "repos" / "testuser__test-repo"
        with patch("backend.github.client.Repo") as mock_repo_cls:
            client = GitHubClient("fake_token")
            result = client.clone_or_pull(
                clone_url="https://github.com/testuser/test-repo.git",
                local_path=local_path,
                token="fake_token",
            )
            assert result == str(local_path)
            mock_repo_cls.clone_from.assert_called_once()
            args, _ = mock_repo_cls.clone_from.call_args
            assert "https://fake_token@" in args[0]
            assert str(local_path) == str(args[1])

    def test_clone_without_token(self, tmp_path: Path, mock_github):
        local_path = tmp_path / "repos" / "testuser__test-repo"
        with patch("backend.github.client.Repo") as mock_repo_cls:
            client = GitHubClient("")
            result = client.clone_or_pull(
                clone_url="https://github.com/testuser/test-repo.git",
                local_path=local_path,
            )
            assert result == str(local_path)
            mock_repo_cls.clone_from.assert_called_once()
            url = mock_repo_cls.clone_from.call_args[0][0]
            assert url == "https://github.com/testuser/test-repo.git"

    def test_pull_existing_repository(self, tmp_path: Path, mock_github):
        local_path = tmp_path / "existing_repo"
        local_path.mkdir(parents=True)
        (local_path / ".git").mkdir()
        with patch("backend.github.client.Repo") as mock_repo_cls:
            mock_local_repo = MagicMock()
            mock_repo_cls.return_value = mock_local_repo
            client = GitHubClient("fake_token")
            result = client.clone_or_pull(
                clone_url="https://github.com/testuser/test-repo.git",
                local_path=local_path,
            )
            assert result == str(local_path)
            mock_repo_cls.clone_from.assert_not_called()
            mock_local_repo.remotes.origin.pull.assert_called_once()

    def test_pull_non_git_directory(self, tmp_path: Path, mock_github):
        local_path = tmp_path / "existing_dir"
        local_path.mkdir(parents=True)
        with patch("backend.github.client.Repo") as mock_repo_cls:
            client = GitHubClient("fake_token")
            client.clone_or_pull(
                clone_url="https://github.com/testuser/test-repo.git",
                local_path=local_path,
            )
            mock_repo_cls.clone_from.assert_called_once()
