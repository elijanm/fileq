# conftest.py - Pytest configuration and shared fixtures

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
    "redis_url": "redis://localhost:6380",  # Different port for tests
    "mongodb_uri": "mongodb://localhost:27018/test_auth_db",  # Test database
    "kratos_url": "http://localhost:4434",  # Admin endpoint for tests
    "base_url": "https://localhost",
    "test_timeout": 30
}

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def docker_services():
    """Start Docker services for integration tests"""
    print("🐳 Starting test Docker services...")
    
    # Start services
    result = subprocess.run(
        ["docker-compose", "-f", "docker-compose.test.yml", "up", "-d"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Failed to start Docker services: {result.stderr}")
        pytest.skip("Docker services failed to start")
    
    # Wait for services to be ready
    print("⏳ Waiting for services to be ready...")
    time.sleep(30)
    
    # Health check
    services_ready = wait_for_services()
    if not services_ready:
        pytest.skip("Services did not become ready in time")
    
    yield
    
    # Cleanup
    print("🧹 Stopping test Docker services...")
    subprocess.run(
        ["docker-compose", "-f", "docker-compose.test.yml", "down", "-v"],
        capture_output=True
    )

def wait_for_services(timeout=60):
    """Wait for services to be ready"""
    import requests
    
    services = [
        ("Auth API", "https://localhost/auth/health"),
        ("Redis", "redis://localhost:6380"),
        ("MongoDB", "mongodb://localhost:27018")
    ]
    
    start_time = time.time()
    
    for service_name, endpoint in services:
        while time.time() - start_time < timeout:
            try:
                if endpoint.startswith("http"):
                    response = requests.get(endpoint, timeout=5, verify=False)
                    if response.status_code == 200:
                        print(f"✅ {service_name} is ready")
                        break
                elif endpoint.startswith("redis"):
                    r = redis.from_url(endpoint)
                    r.ping()
                    print(f"✅ {service_name} is ready")
                    break
                elif endpoint.startswith("mongodb"):
                    client = pymongo.MongoClient(endpoint)
                    client.admin.command('ping')
                    print(f"✅ {service_name} is ready")
                    break
            except Exception as e:
                time.sleep(2)
                continue
        else:
            print(f"❌ {service_name} failed to become ready")
            return False
    
    return True

@pytest.fixture
def test_client():
    """Create test client for API"""
    from main import app
    return TestClient(app)

@pytest.fixture
def clean_database():
    """Clean test database before each test"""
    try:
        client = pymongo.MongoClient(TEST_CONFIG["mongodb_uri"])
        db = client.get_database()
        
        # Clean collections
        db.users.delete_many({})
        db.audit_logs.delete_many({})
        
        yield db
        
        # Cleanup after test
        db.users.delete_many({})
        db.audit_logs.delete_many({})
        
    except Exception as e:
        pytest.skip(f"Database not available: {e}")

@pytest.fixture
def clean_redis():
    """Clean Redis before each test"""
    try:
        r = redis.from_url(TEST_CONFIG["redis_url"])
        r.flushdb()
        
        yield r
        
        # Cleanup after test
        r.flushdb()
        
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")

# Pytest configuration
def pytest_configure(config):
    """Configure pytest"""
    # Add custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests") 
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow running tests")

def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    # Add markers based on file names
    for item in items:
        if "test_auth_api" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "test_integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)

# ---

# # docker-compose.test.yml - Test environment Docker Compose

# version: '3.8'

# services:
#   auth-api-test:
#     build: .
#     ports:
#       - "8001:8000"
#     environment:
#       - KRATOS_PUBLIC_URL=http://kratos-test:4433
#       - REDIS_URL=redis://redis-test:6379
#       - MONGODB_URI=mongodb://mongodb-test:27017/test_auth_db
#       - ENCRYPTION_KEY=test-encryption-key-32-bytes-long
#       - JWT_SECRET=test-jwt-secret-key
#       - AUDIT_RETENTION_DAYS=1
#       - LOG_LEVEL=DEBUG
#       - ENVIRONMENT=test
#     depends_on:
#       - redis-test
#       - kratos-test
#       - mongodb-test
#     networks:
#       - test-network

#   redis-test:
#     image: redis:7-alpine
#     ports:
#       - "6380:6379"
#     networks:
#       - test-network

#   kratos-test:
#     image: oryd/kratos:v1.0.0
#     ports:
#       - "4435:4433"
#       - "4436:4434"
#     environment:
#       - DSN=memory
#       - LOG_LEVEL=debug
#     volumes:
#       - ./kratos:/etc/config/kratos
#     networks:
#       - test-network
#     command: serve -c /etc/config/kratos/kratos.yml --dev

#   mongodb-test:
#     image: mongo:7
#     ports:
#       - "27018:27017"
#     environment:
#       - MONGO_INITDB_DATABASE=test_auth_db
#     networks:
#       - test-network

# networks:
#   test-network:
#     driver: bridge

# ---

# # pytest.ini - Pytest configuration file

# [tool:pytest]
# minversion = 6.0
# addopts = 
#     -ra 
#     --strict-markers 
#     --strict-config 
#     --cov=main
#     --cov-report=html:htmlcov
#     --cov-report=term-missing
#     --cov-fail-under=80
#     --tb=short

# testpaths = 
#     tests

# python_files = test_*.py
# python_classes = Test*
# python_functions = test_*

# markers =
#     unit: Unit tests
#     integration: Integration tests  
#     security: Security tests
#     performance: Performance tests
#     slow: Slow running tests

# filterwarnings =
#     ignore::DeprecationWarning
#     ignore::PendingDeprecationWarning

# ---

# # test_requirements.txt - Additional test dependencies

# pytest==7.4.3
# pytest-asyncio==0.21.1  
# pytest-cov==4.1.0
# pytest-mock==3.12.0
# pytest-xdist==3.5.0
# pytest-html==4.1.1
# pytest-benchmark==4.0.0
# requests==2.31.0
# docker==6.1.3
# psutil==5.9.6
# httpx==0.25.2

# ---


# ---

# # Makefile - Make commands for testing

# .PHONY: test test-unit test-integration test-security test-performance setup cleanup install-deps

# # Default target
# test: test-unit

# # Install test dependencies
# install-deps:
# 	pip install -r test_requirements.txt

# # Setup test environment
# setup:
# 	python run_tests.py --setup

# # Cleanup test environment  
# cleanup:
# 	python run_tests.py --cleanup

# # Run unit