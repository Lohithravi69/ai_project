"""
Integration tests for AI Dev OS Phase 2.

Run with: pytest backend/tests/test_integration.py -v
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.database.base import Base
from backend.database.models import (
    ChunkRecord,
    FileRecord,
    GitHubConnection,
    RepositoryRecord,
)
from backend.main import app
from backend.services.chunking import AdvancedChunker
from backend.services.knowledge_graph import KnowledgeGraphBuilder
from backend.services.embeddings_pipeline import EmbeddingsPipeline


@pytest.fixture
async def test_db():
    """Create an in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    
    async def get_session():
        async with async_session() as session:
            yield session
    
    app.dependency_overrides[__import__("backend.database.session", fromlist=["get_session"]).get_session] = get_session
    
    yield async_session
    
    await engine.dispose()


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestChunking:
    """Test the advanced chunking system."""
    
    @pytest.mark.asyncio
    async def test_chunk_simple_python_file(self, test_db):
        """Test chunking a simple Python file."""
        async with test_db() as session:
            chunker = AdvancedChunker()
            
            code = """
def hello_world():
    '''Simple function.'''
    print("Hello, world!")

class Calculator:
    def add(self, a, b):
        return a + b
"""
            
            repo_id = "test-repo-1"
            file_path = "test.py"
            
            chunks = await chunker.chunk_file(session, repo_id, file_path, code)
            
            assert len(chunks) > 0
            assert any("hello_world" in c.content or "def hello" in c.content for c in chunks)
            assert any("Calculator" in c.content or "class Calculator" in c.content for c in chunks)
    
    @pytest.mark.asyncio
    async def test_chunk_metadata(self, test_db):
        """Test that chunk metadata is populated."""
        async with test_db() as session:
            chunker = AdvancedChunker()
            
            code = "def test_func():\n    pass"
            repo_id = "test-repo-2"
            file_path = "test_func.py"
            
            chunks = await chunker.chunk_file(session, repo_id, file_path, code)
            
            assert len(chunks) > 0
            assert chunks[0].metadata_json is not None
            assert "chunk_type" in chunks[0].metadata_json


class TestKnowledgeGraph:
    """Test the knowledge graph builder."""
    
    @pytest.mark.asyncio
    async def test_build_graph_from_files(self, test_db, tmp_path):
        """Test building a knowledge graph from sample files."""
        # Create sample files
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        
        (repo_dir / "main.py").write_text("def main():\n    pass\n")
        (repo_dir / "utils.py").write_text("def helper():\n    pass\n")
        
        async with test_db() as session:
            kg = KnowledgeGraphBuilder()
            repo_id = "test-repo-3"
            
            result = await kg.build_graph(session, repo_id, repo_dir)
            
            assert result["nodes"] > 0
            assert result["edges"] >= 0


class TestAPI:
    """Test v2 API endpoints."""
    
    def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_semantic_search_endpoint_empty(self, client, test_db):
        """Test semantic search with no data."""
        with patch("backend.embeddings.ollama_client.OllamaClient.embed_text", return_value=[0.1] * 384):
            response = client.post(
                "/api/v2/search/semantic",
                json={"query": "test query", "repository_id": "nonexistent", "top_k": 5},
            )
            # Should handle gracefully
            assert response.status_code in [200, 400]
    
    def test_analyze_repository_endpoint(self, client):
        """Test repository analysis endpoint."""
        response = client.post(
            "/api/v2/repository/analyze",
            json={"repository_id": "test-repo", "repo_root": None},
        )
        # May fail due to missing repo, but endpoint should be callable
        assert response.status_code in [200, 400, 404]
    
    def test_project_health_endpoint(self, client):
        """Test project health endpoint."""
        response = client.post(
            "/api/v2/project/health",
            json={"repository_id": "test-repo", "repo_root": None},
        )
        # May fail due to missing repo, but endpoint should be callable
        assert response.status_code in [200, 400, 404]
    
    def test_project_graph_endpoint(self, client):
        """Test project graph endpoint."""
        response = client.post(
            "/api/v2/repository/graph",
            json={"repository_id": "test-repo", "limit": 100},
        )
        # May fail due to missing repo, but endpoint should be callable
        assert response.status_code in [200, 400]
    
    def test_memory_conversation_endpoint(self, client):
        """Test memory conversation endpoint."""
        response = client.post(
            "/api/v2/memory/conversation",
            json={"repository_id": None, "session_id": None, "limit": 10},
        )
        # Should return empty or success
        assert response.status_code in [200, 400]


class TestIntegration:
    """End-to-end integration tests."""
    
    @pytest.mark.asyncio
    async def test_full_chunking_workflow(self, test_db):
        """Test the full chunking workflow: parse -> chunk -> embed."""
        async with test_db() as session:
            repo_id = "integration-test-1"
            
            # Create a repository record
            repo = RepositoryRecord(
                id=repo_id,
                connection_id="test-connection",
                github_id=123,
                full_name="test/repo",
                clone_url="https://github.com/test/repo",
                local_path="/tmp/test",
                default_branch="main",
            )
            session.add(repo)
            await session.commit()
            
            # Create a file record
            file_record = FileRecord(
                id="file-1",
                repository_id=repo_id,
                path="test.py",
                language="python",
                content_hash="abc123",
            )
            session.add(file_record)
            await session.commit()
            
            # Chunk the file
            chunker = AdvancedChunker()
            code = "def hello():\n    return 'world'\n"
            chunks = await chunker.chunk_file(session, repo_id, "test.py", code)
            
            assert len(chunks) > 0
            
            # Verify chunks were created
            result = await session.execute(
                select(ChunkRecord).where(ChunkRecord.repository_id == repo_id)
            )
            db_chunks = result.scalars().all()
            assert len(db_chunks) > 0


class TestServices:
    """Test individual services."""
    
    @pytest.mark.asyncio
    async def test_embeddings_pipeline_init(self):
        """Test embeddings pipeline initialization."""
        with patch("backend.embeddings.ollama_client.OllamaClient"):
            pipeline = EmbeddingsPipeline()
            assert pipeline is not None
    
    @pytest.mark.asyncio
    async def test_chunker_handles_large_file(self, test_db):
        """Test chunker with a large code file."""
        async with test_db() as session:
            chunker = AdvancedChunker()
            
            # Generate large code
            code = "\n".join([f"def func_{i}():\n    pass\n" for i in range(100)])
            
            chunks = await chunker.chunk_file(session, "test-repo", "large.py", code)
            
            # Should split into multiple chunks
            assert len(chunks) > 1


@pytest.mark.asyncio
async def test_concurrent_operations(test_db):
    """Test concurrent chunking and graph operations."""
    async with test_db() as session:
        repo_id = "concurrent-test"
        
        # Create sample files concurrently
        chunker = AdvancedChunker()
        
        code1 = "def func_a():\n    pass\n"
        code2 = "def func_b():\n    pass\n"
        
        results = await asyncio.gather(
            chunker.chunk_file(session, repo_id, "file1.py", code1),
            chunker.chunk_file(session, repo_id, "file2.py", code2),
        )
        
        assert all(len(r) > 0 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
