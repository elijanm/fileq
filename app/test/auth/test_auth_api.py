import pytest
import time
import jwt
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

# Test data
VALID_USER_DATA = {
    "email": "test@example.com",
    "password": "ValidPassword123!",
    "name": "Test User",
    "terms_accepted": True,
    "marketing_consent": False
}

WEAK_PASSWORDS = [
    "123456",
    "password", 
    "Password1",  # Missing special character
    "Pass!",      # Too short
    "password123!",  # No uppercase
    "PASSWORD123!"   # No lowercase
]

class TestRegistration:
    """Test user registration functionality"""
    
    def test_valid_registration(self, test_client, mock_redis, mock_kratos, mock_lago, mock_db):
        """Test successful user registration"""
        response = test_client.post("/auth/register", json=VALID_USER_DATA)
        
        assert response.status_code == 200
        data = response.json()
        assert data["msg"] == "User registered successfully"
        assert "user_id" in data

    def test_duplicate_email_registration(self, test_client, mock_redis, mock_kratos, mock_lago, mock_db):
        """Test registration with existing email"""
        mock_users, mock_audit = mock_db
        mock_users.find_one.return_value = {"email": "test@example.com"}
        
        response = test_client.post("/auth/register", json=VALID_USER_DATA)
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    @pytest.mark.parametrize("weak_password", WEAK_PASSWORDS)
    def test_weak_password_rejection(self, test_client, weak_password, mock_redis, mock_kratos, mock_lago, mock_db):
        """Test rejection of weak passwords"""
        user_data = VALID_USER_DATA.copy()
        user_data["password"] = weak_password
        
        response = test_client.post("/auth/register", json=user_data)
        
        assert response.status_code == 422

    def test_terms_not_accepted(self, test_client, mock_redis, mock_kratos, mock_lago, mock_db):
        """Test registration fails when terms not accepted"""
        user_data = VALID_USER_DATA.copy()
        user_data["terms_accepted"] = False
        
        response = test_client.post("/auth/register", json=user_data)
        
        assert response.status_code == 422


class TestLogin:
    """Test user login functionality"""
    
    def test_successful_login(self, test_client, mock_redis, mock_db):
        """Test successful login"""
        mock_users, mock_audit = mock_db
        mock_users.find_one.return_value = {
            "email": "test@example.com",
            "kratos_id": "user-123",
            "account_locked": False,
            "failed_login_attempts": 0
        }
        
        with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
            mock_get.return_value.json.return_value = {"id": "login-flow-123"}
            mock_get.return_value.status_code = 200
            
            mock_post.return_value.json.return_value = {
                "identity": {"id": "user-123"}
            }
            mock_post.return_value.status_code = 200
            
            login_data = {
                "email": "test@example.com",
                "password": "ValidPassword123!"
            }
            
            response = test_client.post("/auth/login", json=login_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data

    def test_invalid_credentials(self, test_client, mock_redis, mock_db):
        """Test login with invalid credentials"""
        mock_users, mock_audit = mock_db
        mock_users.find_one.return_value = {
            "email": "test@example.com",
            "account_locked": False,
            "failed_login_attempts": 0
        }
        
        with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
            mock_get.return_value.json.return_value = {"id": "login-flow-123"}
            mock_get.return_value.status_code = 200
            
            mock_post.return_value.status_code = 401
            
            login_data = {
                "email": "test@example.com", 
                "password": "wrongpassword"
            }
            
            response = test_client.post("/auth/login", json=login_data)
            
            assert response.status_code == 401

    def test_locked_account_login(self, test_client, mock_redis, mock_db):
        """Test login attempt on locked account"""
        mock_users, mock_audit = mock_db
        mock_users.find_one.return_value = {
            "email": "test@example.com",
            "account_locked": True
        }
        
        login_data = {
            "email": "test@example.com",
            "password": "ValidPassword123!"
        }
        
        response = test_client.post("/auth/login", json=login_data)
        
        assert response.status_code == 423


class TestPasswordReset:
    """Test password reset functionality"""
    
    def test_password_reset_request(self, test_client, mock_redis):
        """Test password reset request"""
        with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
            mock_get.return_value.json.return_value = {"id": "recovery-flow-123"}
            mock_get.return_value.status_code = 200
            mock_post.return_value.status_code = 200
            
            response = test_client.post("/auth/forgot-password", json="test@example.com")
            
            assert response.status_code == 200

    def test_password_reset_rate_limiting(self, test_client, mock_redis):
        """Test rate limiting on password reset"""
        mock_redis.exists.return_value = True
        
        response = test_client.post("/auth/forgot-password", json="test@example.com")
        
        assert response.status_code == 429


class TestSocialLogin:
    """Test social login functionality"""
    
    @pytest.mark.parametrize("provider", ["google", "github", "facebook", "microsoft"])
    def test_valid_social_providers(self, test_client, provider):
        """Test social login with valid providers"""
        with patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = {"id": "social-flow-123"}
            mock_get.return_value.status_code = 200
            
            response = test_client.get(f"/auth/login/social/{provider}")
            
            assert response.status_code == 200
            data = response.json()
            assert "redirect_url" in data

    def test_invalid_social_provider(self, test_client):
        """Test social login with invalid provider"""
        response = test_client.get("/auth/login/social/invalid-provider")
        
        assert response.status_code == 400


class TestAuthentication:
    """Test authentication middleware"""
    
    def test_whoami_with_valid_token(self, test_client, mock_redis, mock_db):
        """Test /me endpoint with valid token"""
        mock_users, mock_audit = mock_db
        mock_redis.exists.return_value = True
        
        mock_users.find_one.return_value = {
            "kratos_id": "user-123",
            "email": "test@example.com",
            "name": "encrypted-name",
            "created_at": "2025-01-01T12:00:00Z"
        }
        
        with patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = "test-secret-key"
            
            token_payload = {
                "user_id": "user-123",
                "exp": datetime.utcnow() + timedelta(hours=1),
                "jti": "session-123"
            }
            token = jwt.encode(token_payload, "test-secret-key", algorithm="HS256")
            
            with patch('main.SecurityUtils.decrypt_sensitive_data') as mock_decrypt:
                mock_decrypt.return_value = "Test User"
                
                response = test_client.get(
                    "/auth/me",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                assert response.status_code == 200

    def test_whoami_without_token(self, test_client):
        """Test /me endpoint without token"""
        response = test_client.get("/auth/me")
        
        assert response.status_code == 403


class TestHealthCheck:
    """Test health check endpoint"""
    
    def test_health_endpoint(self, test_client, mock_redis, mock_db):
        """Test health check endpoint"""
        mock_users, mock_audit = mock_db
        mock_users.find_one.return_value = {"_id": "test"}
        
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            
            response = test_client.get("/auth/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data


class TestSecurityUtils:
    """Test security utility functions"""
    
    def test_password_hashing(self):
        """Test password hashing"""
        from main import SecurityUtils
        
        password = "TestPassword123!"
        hashed = SecurityUtils.hash_password(password)
        
        assert hashed != password
        assert SecurityUtils.verify_password(password, hashed)

    def test_token_generation(self):
        """Test JWT token generation"""
        from main import SecurityUtils
        
        with patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = "test-secret-key"
            
            token = SecurityUtils.generate_session_token("user-123")
            assert isinstance(token, str)