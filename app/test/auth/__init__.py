"""Test package for authentication API"""

# tests/conftest.py
import pytest
import asyncio
import os
import subprocess
import time
from unittest.mock import MagicMock, patch
import redis
import pymongo
from fastapi.testclient import TestClient

# Test configuration
TEST_CONFIG = {
    "redis_url": "redis://localhost:6380",
    "mongodb_uri": "mongodb://localhost:27018/test_auth_db",
    "kratos_url": "http://localhost:4434",
    "base_url": "https://localhost",
    "test_timeout": 30
}

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_client():
    """Create test client for API"""
    from main import app
    return TestClient(app)

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    with patch('redis.from_url') as mock_redis_client:
        redis_instance = MagicMock()
        redis_instance.get.return_value = None
        redis_instance.exists.return_value = False
        redis_instance.setex.return_value = True
        redis_instance.incr.return_value = 1
        redis_instance.delete.return_value = True
        redis_instance.ping.return_value = True
        mock_redis_client.return_value = redis_instance
        yield redis_instance

@pytest.fixture
def mock_kratos():
    """Mock Kratos API responses"""
    with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
        mock_get.return_value.json.return_value = {"id": "flow-123"}
        mock_get.return_value.status_code = 200
        
        mock_post.return_value.json.return_value = {
            "id": "user-123",
            "created_at": "2025-01-01T12:00:00Z"
        }
        mock_post.return_value.status_code = 200
        
        yield mock_get, mock_post

@pytest.fixture
def mock_lago():
    """Mock Lago billing service"""
    with patch('services.lago_billing.create_customer') as mock_create:
        mock_create.return_value = {
            "customer": {
                "lago_id": "lago-123",
                "external_id": "test@example.com"
            }
        }
        yield mock_create

@pytest.fixture
def mock_db():
    """Mock database operations"""
    with patch('db.users') as mock_users, patch('db.audit_logs') as mock_audit:
        mock_users.find_one.return_value = None
        mock_users.insert_one.return_value = MagicMock()
        mock_users.update_one.return_value = MagicMock()
        
        mock_audit.insert_one.return_value = MagicMock()
        
        yield mock_users, mock_audit