from __future__ import annotations

from pathlib import Path


def repository_folder_name(full_name: str) -> str:
    return full_name.replace("/", "__")


def repository_local_path(root: str, full_name: str) -> Path:
    return Path(root) / repository_folder_name(full_name)
