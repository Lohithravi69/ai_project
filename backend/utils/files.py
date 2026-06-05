from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path

IGNORED_DIRECTORY_NAMES = {".git", "node_modules", "venv", ".venv", "dist", "build", "__pycache__", ".next"}
IGNORED_FILE_NAMES = {".DS_Store", "Thumbs.db"}
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".yaml", ".yml", ".toml", ".txt", ".html", ".css", ".scss", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp", ".php", ".rb", ".sh", ".sql"
}
LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".json": "json",
    ".md": "markdown",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sh": "shell",
    ".sql": "sql",
}


def should_ignore_path(path: Path) -> bool:
    """Return True when a path should be excluded from scans."""

    if path.name in IGNORED_FILE_NAMES:
        return True
    return any(part in IGNORED_DIRECTORY_NAMES for part in path.parts)


def iter_text_files(root: Path) -> Iterable[Path]:
    """Yield files that are likely to contain code or documentation."""

    for file_path in root.rglob("*"):
        if file_path.is_file() and not should_ignore_path(file_path):
            if file_path.suffix.lower() in TEXT_EXTENSIONS or file_path.name in {
                "package.json",
                "requirements.txt",
                "pyproject.toml",
                "Pipfile",
                "Dockerfile",
                "docker-compose.yml",
                "docker-compose.yaml",
                "next.config.js",
                "tailwind.config.js",
                "tailwind.config.ts",
            }:
                yield file_path


def detect_language(file_path: Path) -> str:
    return LANGUAGE_BY_EXTENSION.get(file_path.suffix.lower(), "unknown")


def safe_read_text(file_path: Path, max_bytes: int) -> str:
    data = file_path.read_bytes()
    if len(data) > max_bytes:
        return ""
    return data.decode("utf-8", errors="ignore")


def hash_content(content: str) -> str:
    return sha256(content.encode("utf-8", errors="ignore")).hexdigest()


def chunk_text(content: str, max_chars: int = 4000) -> list[str]:
    """Split large text into semantic-friendly chunks without external dependencies."""

    if not content:
        return []
    lines = content.splitlines()
    chunks: list[str] = []
    buffer: list[str] = []
    size = 0
    for line in lines:
        line_size = len(line) + 1
        if buffer and size + line_size > max_chars:
            chunks.append("\n".join(buffer).strip())
            buffer = []
            size = 0
        buffer.append(line)
        size += line_size
    if buffer:
        chunks.append("\n".join(buffer).strip())
    return [chunk for chunk in chunks if chunk]
