from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from github import Github
from git import Repo


@dataclass
class GitHubRepositoryInfo:
    github_id: int
    full_name: str
    clone_url: str
    default_branch: str
    description: str | None
    language: str | None
    stars: int
    forks: int
    metadata: dict[str, Any]


class GitHubClient:
    """Thin wrapper around PyGithub and GitPython for repository sync operations."""

    def __init__(self, token: str) -> None:
        self.token = token
        self._client = Github(token) if token else Github()

    def get_user_login(self) -> str:
        return self._client.get_user().login

    def list_repositories(self) -> list[GitHubRepositoryInfo]:
        repositories: list[GitHubRepositoryInfo] = []
        for repo in self._client.get_user().get_repos():
            repositories.append(
                GitHubRepositoryInfo(
                    github_id=repo.id,
                    full_name=repo.full_name,
                    clone_url=repo.clone_url,
                    default_branch=repo.default_branch or "main",
                    description=repo.description,
                    language=repo.language,
                    stars=repo.stargazers_count,
                    forks=repo.forks_count,
                    metadata={
                        "private": repo.private,
                        "archived": repo.archived,
                        "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                    },
                )
            )
        return repositories

    def clone_or_pull(self, clone_url: str, local_path: Path, token: str | None = None) -> str:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if local_path.exists() and (local_path / ".git").exists():
            repo = Repo(local_path)
            repo.remotes.origin.pull()
            return str(local_path)

        authenticated_url = clone_url
        if token and authenticated_url.startswith("https://"):
            authenticated_url = authenticated_url.replace("https://", f"https://{token}@", 1)
        Repo.clone_from(authenticated_url, local_path)
        return str(local_path)
