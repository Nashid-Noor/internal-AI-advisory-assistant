"""
Pytest Configuration and Fixtures

Shared fixtures for all tests.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Set test environment before imports
os.environ["APP_ENV"] = "testing"
os.environ["AUTH_ENABLED"] = "false"


@pytest.fixture(scope="session")
def temp_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    mock = MagicMock()
    mock.generate = AsyncMock(return_value='{"summary": "Test response"}')
    mock.generate_json = AsyncMock(return_value={"summary": "Test response"})
    return mock


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service for testing."""
    mock = MagicMock()
    mock.embed_text = AsyncMock(return_value=[0.1] * 1536)
    mock.embed_texts = AsyncMock(return_value=[[0.1] * 1536])
    mock.dimension = 1536
    return mock


@pytest.fixture
def mock_vector_store():
    """Mock vector store for testing."""
    mock = MagicMock()
    mock.search = AsyncMock(return_value=[])
    mock.add_chunks = AsyncMock(return_value=1)
    mock.initialize = AsyncMock()
    return mock


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    from app.core.security import User, UserRole
    
    return User(
        user_id="test-user",
        role=UserRole.CONSULTANT,
        email="test@example.com",
    )


@pytest.fixture
def sample_query_request():
    """Create a sample query request."""
    from app.models.queries import QueryRequest
    
    return QueryRequest(
        query="What are the key risks for this project?",
    )
