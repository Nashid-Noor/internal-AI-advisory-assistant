"""
Integration Tests for API Endpoints

These tests require a running application but mock external services.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from app.main import app
from app.models.queries import TaskType


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Standard authentication headers."""
    return {
        "X-API-Key": "dev-key-change-me",
        "X-User-ID": "test-user",
        "X-User-Role": "consultant",
    }


class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    def test_health_check(self, client):
        """Basic health check should return 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_system_info(self, client):
        """System info should return configuration details."""
        response = client.get("/api/v1/health/info")
        assert response.status_code == 200
        
        data = response.json()
        assert "app_name" in data
        assert "version" in data
        assert "features" in data


class TestQueryEndpoints:
    """Tests for query endpoints."""
    
    def test_list_task_types(self, client, auth_headers):
        """Should return list of available task types."""
        response = client.get("/api/v1/query/task-types", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "task_types" in data
        assert len(data["task_types"]) > 0
        
        # Verify structure
        for task in data["task_types"]:
            assert "type" in task
            assert "description" in task
    
    @patch("app.workflows.orchestrator.get_orchestrator")
    def test_query_request_validation(self, mock_orchestrator, client, auth_headers):
        """Query endpoint should validate request body."""
        # Empty query should fail
        response = client.post(
            "/api/v1/query",
            json={"query": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422
        
        # Query too short should fail
        response = client.post(
            "/api/v1/query",
            json={"query": "hi"},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestAuthenticationMiddleware:
    """Tests for authentication."""
    
    def test_missing_api_key(self, client):
        """Requests without API key should be rejected."""
        response = client.post(
            "/api/v1/query",
            json={"query": "What are the risks?"},
            headers={"X-User-ID": "test", "X-User-Role": "analyst"},
        )
        assert response.status_code == 401
    
    def test_invalid_api_key(self, client):
        """Requests with invalid API key should be rejected."""
        response = client.post(
            "/api/v1/query",
            json={"query": "What are the risks?"},
            headers={
                "X-API-Key": "invalid-key",
                "X-User-ID": "test",
                "X-User-Role": "analyst",
            },
        )
        assert response.status_code == 401


class TestFeedbackEndpoints:
    """Tests for feedback endpoints."""
    
    def test_feedback_stats_requires_partner(self, client, auth_headers):
        """Feedback stats should require Partner role."""
        # Consultant should be denied
        response = client.get(
            "/api/v1/feedback/stats",
            headers=auth_headers,  # consultant role
        )
        assert response.status_code == 403
        
        # Partner should be allowed
        partner_headers = {
            "X-API-Key": "dev-key-change-me",
            "X-User-ID": "test-partner",
            "X-User-Role": "partner",
        }
        response = client.get(
            "/api/v1/feedback/stats",
            headers=partner_headers,
        )
        assert response.status_code == 200


class TestRootEndpoint:
    """Tests for root endpoint."""
    
    def test_root_returns_info(self, client):
        """Root endpoint should return basic info."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "docs" in data
