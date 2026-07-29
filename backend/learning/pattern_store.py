from __future__ import annotations

import json
import os
from typing import Any

PATTERNS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "patterns")


class Pattern:
    def __init__(
        self,
        name: str = "",
        description: str = "",
        category: str = "",
        template_code: str = "",
        dependencies: list[str] | None = None,
        best_practices: list[str] | None = None,
        related_patterns: list[str] | None = None,
    ) -> None:
        self.name: str = name
        self.description: str = description
        self.category: str = category
        self.template_code: str = template_code
        self.dependencies: list[str] = dependencies or []
        self.best_practices: list[str] = best_practices or []
        self.related_patterns: list[str] = related_patterns or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "template_code": self.template_code,
            "dependencies": self.dependencies,
            "best_practices": self.best_practices,
            "related_patterns": self.related_patterns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pattern:
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            category=data.get("category", ""),
            template_code=data.get("template_code", ""),
            dependencies=data.get("dependencies", []),
            best_practices=data.get("best_practices", []),
            related_patterns=data.get("related_patterns", []),
        )


_BUILTIN_PATTERNS: list[dict[str, Any]] = [
    {
        "name": "JWT Authentication",
        "description": "JSON Web Token based authentication middleware for FastAPI",
        "category": "authentication",
        "template_code": (
            "from datetime import datetime, timedelta, timezone\n"
            "from jose import JWTError, jwt\n"
            "from passlib.context import CryptContext\n\n"
            "SECRET_KEY = 'change-me'\n"
            "ALGORITHM = 'HS256'\n"
            "ACCESS_TOKEN_EXPIRE_MINUTES = 30\n\n"
            "pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')\n\n"
            "def verify_password(plain: str, hashed: str) -> bool:\n"
            "    return pwd_context.verify(plain, hashed)\n\n"
            "def get_password_hash(password: str) -> str:\n"
            "    return pwd_context.hash(password)\n\n"
            "def create_access_token(data: dict) -> str:\n"
            "    to_encode = data.copy()\n"
            "    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)\n"
            "    to_encode.update({'exp': expire})\n"
            "    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)\n\n"
            "def decode_access_token(token: str) -> dict | None:\n"
            "    try:\n"
            "        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])\n"
            "    except JWTError:\n"
            "        return None"
        ),
        "dependencies": ["python-jose[cryptography]", "passlib[bcrypt]"],
        "best_practices": [
            "Rotate SECRET_KEY in production via environment variable",
            "Use short token expiry (15-30 minutes)",
            "Store hashed passwords, never plaintext",
        ],
        "related_patterns": ["CRUD APIs", "Error handling"],
    },
    {
        "name": "CRUD APIs",
        "description": "Standard Create-Read-Update-Delete endpoints for a resource",
        "category": "api",
        "template_code": (
            "from fastapi import APIRouter, Depends, HTTPException, status\n"
            "from sqlalchemy.ext.asyncio import AsyncSession\n"
            "from app.database import get_session\n"
            "from app.models import Item\n"
            "from app.schemas import ItemCreate, ItemRead, ItemUpdate\n\n"
            "router = APIRouter(prefix='/items', tags=['items'])\n\n"
            "@router.post('/', response_model=ItemRead, status_code=status.HTTP_201_CREATED)\n"
            "async def create_item(data: ItemCreate, session: AsyncSession = Depends(get_session)):\n"
            "    item = Item(**data.model_dump())\n"
            "    session.add(item)\n"
            "    await session.commit()\n"
            "    await session.refresh(item)\n"
            "    return item\n\n"
            "@router.get('/{item_id}', response_model=ItemRead)\n"
            "async def read_item(item_id: str, session: AsyncSession = Depends(get_session)):\n"
            "    item = await session.get(Item, item_id)\n"
            "    if not item:\n"
            "        raise HTTPException(status_code=404, detail='Item not found')\n"
            "    return item\n\n"
            "@router.put('/{item_id}', response_model=ItemRead)\n"
            "async def update_item(item_id: str, data: ItemUpdate, session: AsyncSession = Depends(get_session)):\n"
            "    item = await session.get(Item, item_id)\n"
            "    if not item:\n"
            "        raise HTTPException(status_code=404, detail='Item not found')\n"
            "    for key, val in data.model_dump(exclude_unset=True).items():\n"
            "        setattr(item, key, val)\n"
            "    await session.commit()\n"
            "    await session.refresh(item)\n"
            "    return item\n\n"
            "@router.delete('/{item_id}', status_code=status.HTTP_204_NO_CONTENT)\n"
            "async def delete_item(item_id: str, session: AsyncSession = Depends(get_session)):\n"
            "    item = await session.get(Item, item_id)\n"
            "    if not item:\n"
            "        raise HTTPException(status_code=404, detail='Item not found')\n"
            "    await session.delete(item)\n"
            "    await session.commit()"
        ),
        "dependencies": ["fastapi", "sqlalchemy[asyncio]"],
        "best_practices": [
            "Use Pydantic schemas for request/response validation",
            "Return 404 for missing resources",
            "Use 201 for creation, 204 for deletion",
        ],
        "related_patterns": ["Pagination", "Error handling"],
    },
    {
        "name": "Pagination",
        "description": "Offset-based pagination for list endpoints",
        "category": "api",
        "template_code": (
            "from typing import Generic, TypeVar\n"
            "from pydantic import BaseModel\n"
            "from sqlalchemy import select, func\n\n"
            "T = TypeVar('T')\n\n"
            "class PaginatedResponse(BaseModel, Generic[T]):\n"
            "    items: list[T]\n"
            "    total: int\n"
            "    page: int\n"
            "    page_size: int\n"
            "    total_pages: int\n\n"
            "async def paginate(session, query, page: int = 1, page_size: int = 20):\n"
            "    count_q = select(func.count()).select_from(query.subquery())\n"
            "    total = (await session.execute(count_q)).scalar() or 0\n"
            "    offset = (page - 1) * page_size\n"
            "    result = await session.execute(query.offset(offset).limit(page_size))\n"
            "    items = list(result.scalars().all())\n"
            "    return PaginatedResponse(\n"
            "        items=items,\n"
            "        total=total,\n"
            "        page=page,\n"
            "        page_size=page_size,\n"
            "        total_pages=-(-total // page_size),\n"
            "    )"
        ),
        "dependencies": ["pydantic", "sqlalchemy"],
        "best_practices": [
            "Always return total count for pagination UI",
            "Cap page_size to prevent abuse",
            "Use cursor-based pagination for real-time data",
        ],
        "related_patterns": ["CRUD APIs"],
    },
    {
        "name": "Logging",
        "description": "Structured logging setup with rotation and request IDs",
        "category": "infrastructure",
        "template_code": (
            "import logging\n"
            "import sys\n"
            "from uuid import uuid4\n\n"
            "from loguru import logger\n\n"
            "def setup_logging(service_name: str = 'app'):\n"
            "    logger.remove()\n"
            "    logger.add(\n"
            "        sys.stderr,\n"
            "        format='{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:7} | {extra[request_id]:36} | {message}',\n"
            "        level='INFO',\n"
            "    )\n"
            "    logger.add(\n"
            "        f'logs/{service_name}.log',\n"
            "        rotation='10 MB',\n"
            "        retention='30 days',\n"
            "        format='{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:7} | {extra[request_id]:36} | {message}',\n"
            "    )\n"
            "    logger = logger.bind(request_id=str(uuid4()))\n"
            "    return logger"
        ),
        "dependencies": ["loguru"],
        "best_practices": [
            "Use structured logging (JSON) in production",
            "Include request_id for traceability",
            "Rotate logs to manage disk usage",
        ],
        "related_patterns": ["Error handling"],
    },
    {
        "name": "Repository Pattern",
        "description": "Data access layer separating business logic from ORM",
        "category": "architecture",
        "template_code": (
            "from abc import ABC, abstractmethod\n"
            "from sqlalchemy import select\n"
            "from sqlalchemy.ext.asyncio import AsyncSession\n\n"
            "class BaseRepository(ABC):\n"
            "    def __init__(self, session: AsyncSession):\n"
            "        self._session = session\n\n"
            "class ItemRepository(BaseRepository):\n"
            "    async def get_by_id(self, item_id: str):\n"
            "        return await self._session.get(Item, item_id)\n\n"
            "    async def list_all(self, skip: int = 0, limit: int = 100):\n"
            "        result = await self._session.execute(\n"
            "            select(Item).offset(skip).limit(limit)\n"
            "        )\n"
            "        return list(result.scalars().all())\n\n"
            "    async def add(self, item: Item) -> Item:\n"
            "        self._session.add(item)\n"
            "        await self._session.commit()\n"
            "        await self._session.refresh(item)\n"
            "        return item\n\n"
            "    async def delete(self, item: Item) -> None:\n"
            "        await self._session.delete(item)\n"
            "        await self._session.commit()"
        ),
        "dependencies": ["sqlalchemy[asyncio]"],
        "best_practices": [
            "Keep repositories focused on a single entity",
            "Do not leak ORM session outside repository",
            "Use interfaces (ABC) for testability",
        ],
        "related_patterns": ["CRUD APIs", "Error handling"],
    },
    {
        "name": "Error Handling",
        "description": "Centralized exception handling and error responses for FastAPI",
        "category": "infrastructure",
        "template_code": (
            "from fastapi import FastAPI, Request\n"
            "from fastapi.responses import JSONResponse\n\n"
            "class AppException(Exception):\n"
            "    def __init__(self, message: str, status_code: int = 400):\n"
            "        self.message = message\n"
            "        self.status_code = status_code\n\n"
            "def register_error_handlers(app: FastAPI):\n"
            "    @app.exception_handler(AppException)\n"
            "    async def app_exception_handler(request: Request, exc: AppException):\n"
            "        return JSONResponse(\n"
            "            status_code=exc.status_code,\n"
            "            content={'detail': exc.message, 'type': 'app_error'},\n"
            "        )\n\n"
            "    @app.exception_handler(Exception)\n"
            "    async def unhandled_exception_handler(request: Request, exc: Exception):\n"
            "        return JSONResponse(\n"
            "            status_code=500,\n"
            "            content={'detail': 'Internal server error', 'type': 'server_error'},\n"
            "        )"
        ),
        "dependencies": ["fastapi"],
        "best_practices": [
            "Never leak stack traces to API responses",
            "Log full exception details server-side",
            "Use typed exceptions for different error categories",
        ],
        "related_patterns": ["Logging", "CRUD APIs"],
    },
    {
        "name": "React Form",
        "description": "Controlled form component with validation using React Hook Form",
        "category": "frontend",
        "template_code": (
            "import React from 'react'\n"
            "import { useForm } from 'react-hook-form'\n\n"
            "interface FormData {\n"
            "  name: string\n"
            "  email: string\n"
            "}\n\n"
            "export function MyForm() {\n"
            "  const { register, handleSubmit, formState: { errors } } = useForm<FormData>()\n\n"
            "  const onSubmit = (data: FormData) => {\n"
            "    console.log(data)\n"
            "  }\n\n"
            "  return (\n"
            "    <form onSubmit={handleSubmit(onSubmit)}>\n"
            "      <div>\n"
            "        <label>Name</label>\n"
            "        <input {...register('name', { required: 'Name is required' })} />\n"
            "        {errors.name && <span>{errors.name.message}</span>}\n"
            "      </div>\n"
            "      <div>\n"
            "        <label>Email</label>\n"
            "        <input {...register('email', {\n"
            "          required: 'Email is required',\n"
            "          pattern: { value: /^\\S+@\\S+$/i, message: 'Invalid email' },\n"
            "        })} />\n"
            "        {errors.email && <span>{errors.email.message}</span>}\n"
            "      </div>\n"
            "      <button type='submit'>Submit</button>\n"
            "    </form>\n"
            "  )\n"
            "}"
        ),
        "dependencies": ["react-hook-form", "@hookform/resolvers"],
        "best_practices": [
            "Use TypeScript for form data types",
            "Validate on both client and server",
            "Show inline validation errors for better UX",
        ],
        "related_patterns": ["CRUD APIs"],
    },
    {
        "name": "Unit Test Pattern",
        "description": "Pytest-based unit test structure with fixtures and mocking",
        "category": "testing",
        "template_code": (
            "import pytest\n"
            "from unittest.mock import AsyncMock, patch\n\n"
            "@pytest.fixture\n"
            "def mock_session():\n"
            "    return AsyncMock()\n\n"
            "@pytest.mark.asyncio\n"
            "async def test_create_item(mock_session):\n"
            "    from app.repositories import ItemRepository\n"
            "    repo = ItemRepository(mock_session)\n"
            "    item = await repo.get_by_id('test-id')\n"
            "    assert item is not None"
        ),
        "dependencies": ["pytest", "pytest-asyncio"],
        "best_practices": [
            "Use fixtures for shared setup",
            "Mock external dependencies",
            "Test one behavior per test function",
        ],
        "related_patterns": [],
    },
]


def _ensure_builtins(directory: str) -> None:
    index_path = os.path.join(directory, "index.json")
    if os.path.isfile(index_path):
        return
    os.makedirs(directory, exist_ok=True)
    index: dict[str, dict[str, Any]] = {}
    for pdata in _BUILTIN_PATTERNS:
        name = pdata["name"]
        file_path = os.path.join(directory, f"{name.lower().replace(' ', '_')}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(pdata, f, indent=2)
        index[name] = {
            "category": pdata["category"],
            "description": pdata["description"][:200],
            "dependencies": pdata.get("dependencies", []),
        }
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)


class PatternStore:
    def __init__(self, directory: str = PATTERNS_DIR) -> None:
        self._directory = directory
        _ensure_builtins(directory)
        self._index_path = os.path.join(directory, "index.json")
        self._index: dict[str, dict[str, Any]] = {}
        self._load_index()

    def _load_index(self) -> None:
        if os.path.isfile(self._index_path):
            try:
                with open(self._index_path, encoding="utf-8") as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._index = {}

    def _save_index(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def get(self, name: str) -> Pattern | None:
        fname = f"{name.lower().replace(' ', '_')}.json"
        file_path = os.path.join(self._directory, fname)
        if not os.path.isfile(file_path):
            return None
        try:
            with open(file_path, encoding="utf-8") as f:
                return Pattern.from_dict(json.load(f))
        except (json.JSONDecodeError, OSError):
            return None

    def list_patterns(self, category: str | None = None) -> list[Pattern]:
        patterns: list[Pattern] = []
        for name in self._index:
            if category and self._index[name].get("category") != category:
                continue
            p = self.get(name)
            if p:
                patterns.append(p)
        return patterns

    def store(self, pattern: Pattern) -> None:
        fname = f"{pattern.name.lower().replace(' ', '_')}.json"
        file_path = os.path.join(self._directory, fname)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(pattern.to_dict(), f, indent=2)
        self._index[pattern.name] = {
            "category": pattern.category,
            "description": pattern.description[:200],
            "dependencies": pattern.dependencies,
        }
        self._save_index()

    def search_patterns(self, query: str) -> list[Pattern]:
        query_lower = query.lower()
        results: list[Pattern] = []
        for name in self._index:
            if query_lower in name.lower():
                p = self.get(name)
                if p:
                    results.append(p)
        return results

    def get_by_category(self, category: str) -> list[Pattern]:
        return self.list_patterns(category=category)

    def count(self) -> int:
        return len(self._index)
