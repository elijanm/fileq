# tests/test_user_service.py - Comprehensive tests for UserService

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

from services.user_service import (
    UserService, 
    RegistrationRequest, 
    LoginRequest, 
    UserStatus,
    UserProfile
)
from utils.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    AccountLockedError,
    RateLimitExceededError,
    ServiceUnavailableError
)

class TestUserService:
    """Test UserService class"""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for UserService"""
        return {
            'users_collection': MagicMock(),
            'redis_client': MagicMock(),
            'kratos_service': AsyncMock(),
            'lago_service': AsyncMock(),
            'email_service': AsyncMock(),
            'audit_service': AsyncMock(),
            'security_utils': MagicMock()
        }
    
    @pytest.fixture
    def user_service(self, mock_dependencies):
        """Create UserService instance with mocked dependencies"""
        return UserService(**mock_dependencies)
    
    @pytest.fixture
    def valid_registration_request(self):
        """Valid registration request data"""
        return RegistrationRequest(
            email="test@example.com",
            password="ValidPassword123!",
            name="Test User",
            terms_accepted=True,
            marketing_consent=False
        )
    
    @pytest.fixture
    def valid_login_request(self):
        """Valid login request data"""
        return LoginRequest(
            email="test@example.com",
            password="ValidPassword123!",
            ip_address="127.0.0.1",
            user_agent="Test Browser"
        )
    
    @pytest.fixture
    def sample_user_data(self):
        """Sample user data from database"""
        return {
            "_id": "user_object_id",
            "email": "test@example.com",
            "name": "encrypted_name",
            "kratos_id": "kratos_123",
            "lago_customer_id": "lago_123",
            "status": UserStatus.ACTIVE.value,
            "created_at": datetime.utcnow(),
            "account_locked": False,
            "failed_login_attempts": 0,
            "is_verified": True,
            "preferences": {}
        }


class TestUserRegistration:
    """Test user registration functionality"""
    
    @pytest.mark.asyncio
    async def test_successful_user_registration(self, user_service, mock_dependencies, valid_registration_request):
        """Test successful user registration"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = None  # User doesn't exist
        mock_dependencies['redis_client'].get.return_value = None  # No rate limiting
        mock_dependencies['security_utils'].validate_password_strength.return_value = True
        mock_dependencies['security_utils'].encrypt_sensitive_data.return_value = "encrypted_name"
        
        # Mock Kratos response
        kratos_user = {"id": "kratos_123", "created_at": "2025-01-01T12:00:00Z"}
        mock_dependencies['kratos_service'].create_user.return_value = kratos_user
        
        # Mock Lago response
        lago_customer = {
            "customer": {
                "lago_id": "lago_123",
                "external_id": "test@example.com"
            }
        }
        mock_dependencies['lago_service'].create_customer.return_value = lago_customer
        
        # Mock database insertion
        mock_dependencies['users_collection'].insert_one.return_value = MagicMock(inserted_id="user_id_123")
        
        # Execute registration
        result = await user_service.register_user(valid_registration_request, "127.0.0.1")
        
        # Assertions
        assert result["user_id"] == "kratos_123"
        assert result["email"] == "test@example.com"
        assert result["status"] == UserStatus.PENDING_VERIFICATION.value
        assert result["verification_required"] == True
        
        # Verify service calls
        mock_dependencies['kratos_service'].create_user.assert_called_once()
        mock_dependencies['lago_service'].create_customer.assert_called_once()
        mock_dependencies['users_collection'].insert_one.assert_called_once()
        mock_dependencies['email_service'].send_verification_email.assert_called_once()
        mock_dependencies['audit_service'].log_event.assert_called()

    @pytest.mark.asyncio
    async def test_registration_duplicate_email(self, user_service, mock_dependencies, valid_registration_request):
        """Test registration with existing email"""
        # Setup mocks - user already exists
        mock_dependencies['users_collection'].find_one.return_value = {"email": "test@example.com"}
        mock_dependencies['redis_client'].get.return_value = None
        mock_dependencies['security_utils'].validate_password_strength.return_value = True
        
        # Execute and assert exception
        with pytest.raises(UserAlreadyExistsError):
            await user_service.register_user(valid_registration_request, "127.0.0.1")
        
        # Verify audit log
        mock_dependencies['audit_service'].log_event.assert_called_with(
            "registration_attempt_duplicate_email",
            ip_address="127.0.0.1",
            details={"email": "test@example.com"},
            severity="warning"
        )

    @pytest.mark.asyncio
    async def test_registration_rate_limiting(self, user_service, mock_dependencies, valid_registration_request):
        """Test registration rate limiting"""
        # Setup mocks - rate limit exceeded
        mock_dependencies['redis_client'].get.return_value = b'3'  # Max attempts reached
        
        # Execute and assert exception
        with pytest.raises(RateLimitExceededError):
            await user_service.register_user(valid_registration_request, "127.0.0.1")

    @pytest.mark.asyncio
    async def test_registration_weak_password(self, user_service, mock_dependencies, valid_registration_request):
        """Test registration with weak password"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = None
        mock_dependencies['redis_client'].get.return_value = None
        mock_dependencies['security_utils'].validate_password_strength.return_value = False
        
        # Execute and assert exception
        with pytest.raises(ValueError, match="Password does not meet security requirements"):
            await user_service.register_user(valid_registration_request, "127.0.0.1")

    @pytest.mark.asyncio
    async def test_registration_terms_not_accepted(self, user_service, mock_dependencies):
        """Test registration without accepting terms"""
        # Create request without terms acceptance
        request = RegistrationRequest(
            email="test@example.com",
            password="ValidPassword123!",
            name="Test User",
            terms_accepted=False
        )
        
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = None
        mock_dependencies['redis_client'].get.return_value = None
        mock_dependencies['security_utils'].validate_password_strength.return_value = True
        
        # Execute and assert exception
        with pytest.raises(ValueError, match="Terms and conditions must be accepted"):
            await user_service.register_user(request, "127.0.0.1")

    @pytest.mark.asyncio
    async def test_registration_kratos_service_failure(self, user_service, mock_dependencies, valid_registration_request):
        """Test registration when Kratos service fails"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = None
        mock_dependencies['redis_client'].get.return_value = None
        mock_dependencies['security_utils'].validate_password_strength.return_value = True
        mock_dependencies['kratos_service'].create_user.side_effect = Exception("Kratos down")
        
        # Execute and assert exception
        with pytest.raises(ServiceUnavailableError):
            await user_service.register_user(valid_registration_request, "127.0.0.1")

    @pytest.mark.asyncio
    async def test_registration_with_referral(self, user_service, mock_dependencies):
        """Test registration with referral code"""
        # Create request with referral
        request = RegistrationRequest(
            email="test@example.com",
            password="ValidPassword123!",
            name="Test User",
            terms_accepted=True,
            referral_code="REF123"
        )
        
        # Setup mocks
        mock_dependencies['users_collection'].find_one.side_effect = [
            None,  # First call - user doesn't exist
            {"user_id": "referrer_123", "referral_code": "REF123"}  # Second call - referrer exists
        ]
        mock_dependencies['redis_client'].get.return_value = None
        mock_dependencies['security_utils'].validate_password_strength.return_value = True
        mock_dependencies['security_utils'].encrypt_sensitive_data.return_value = "encrypted_name"
        mock_dependencies['kratos_service'].create_user.return_value = {"id": "kratos_123"}
        mock_dependencies['lago_service'].create_customer.return_value = {
            "customer": {"lago_id": "lago_123", "external_id": "test@example.com"}
        }
        mock_dependencies['users_collection'].insert_one.return_value = MagicMock(inserted_id="user_id_123")
        
        # Execute registration
        result = await user_service.register_user(request, "127.0.0.1")
        
        # Verify referral was processed
        assert result["user_id"] == "kratos_123"
        mock_dependencies['users_collection'].update_one.assert_called()  # Referrer count updated


class TestUserAuthentication:
    """Test user authentication functionality"""
    
    @pytest.mark.asyncio
    async def test_successful_authentication(self, user_service, mock_dependencies, valid_login_request, sample_user_data):
        """Test successful user authentication"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = sample_user_data
        mock_dependencies['redis_client'].get.return_value = None  # No rate limiting
        mock_dependencies['kratos_service'].authenticate.return_value = {"session": "kratos_session"}
        mock_dependencies['security_utils'].generate_session_token.return_value = "jwt_token_123"
        mock_dependencies['security_utils'].extract_session_id.return_value = "session_123"
        mock_dependencies['security_utils'].decrypt_sensitive_data.return_value = "Test User"
        
        # Execute authentication
        result = await user_service.authenticate_user(valid_login_request)
        
        # Assertions
        assert result["access_token"] == "jwt_token_123"
        assert result["token_type"] == "bearer"
        assert "user" in result
        assert "session_id" in result
        
        # Verify service calls
        mock_dependencies['kratos_service'].authenticate.assert_called_once()
        mock_dependencies['users_collection'].update_one.assert_called()  # Login info updated
        mock_dependencies['audit_service'].log_event.assert_called()

    @pytest.mark.asyncio
    async def test_authentication_user_not_found(self, user_service, mock_dependencies, valid_login_request):
        """Test authentication with non-existent user"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = None
        mock_dependencies['redis_client'].get.return_value = None
        
        # Execute and assert exception
        with pytest.raises(InvalidCredentialsError):
            await user_service.authenticate_user(valid_login_request)

    @pytest.mark.asyncio
    async def test_authentication_account_locked(self, user_service, mock_dependencies, valid_login_request, sample_user_data):
        """Test authentication with locked account"""
        # Setup mocks - locked account
        locked_user_data = sample_user_data.copy()
        locked_user_data["account_locked"] = True
        
        mock_dependencies['users_collection'].find_one.return_value = locked_user_data
        mock_dependencies['redis_client'].get.return_value = None
        
        # Execute and assert exception
        with pytest.raises(AccountLockedError):
            await user_service.authenticate_user(valid_login_request)

    @pytest.mark.asyncio
    async def test_authentication_rate_limiting(self, user_service, mock_dependencies, valid_login_request):
        """Test authentication rate limiting"""
        # Setup mocks - rate limit exceeded
        mock_dependencies['redis_client'].get.return_value = b'5'  # Max attempts reached
        
        # Execute and assert exception
        with pytest.raises(RateLimitExceededError):
            await user_service.authenticate_user(valid_login_request)

    @pytest.mark.asyncio
    async def test_authentication_invalid_credentials(self, user_service, mock_dependencies, valid_login_request, sample_user_data):
        """Test authentication with invalid credentials"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = sample_user_data
        mock_dependencies['redis_client'].get.return_value = None
        mock_dependencies['kratos_service'].authenticate.side_effect = Exception("Invalid credentials")
        
        # Execute and assert exception
        with pytest.raises(InvalidCredentialsError):
            await user_service.authenticate_user(valid_login_request)
        
        # Verify failed login handling
        mock_dependencies['users_collection'].update_one.assert_called()  # Failed attempts updated

    @pytest.mark.asyncio
    async def test_authentication_account_lockout_after_max_attempts(self, user_service, mock_dependencies, valid_login_request, sample_user_data):
        """Test account lockout after max failed attempts"""
        # Setup user with 4 failed attempts (5th will trigger lockout)
        user_data = sample_user_data.copy()
        user_data["failed_login_attempts"] = 4
        
        mock_dependencies['users_collection'].find_one.return_value = user_data
        mock_dependencies['redis_client'].get.return_value = None
        mock_dependencies['kratos_service'].authenticate.side_effect = Exception("Invalid credentials")
        
        # Execute authentication (should fail and trigger lockout)
        with pytest.raises(InvalidCredentialsError):
            await user_service.authenticate_user(valid_login_request)
        
        # Verify account was locked
        update_call = mock_dependencies['users_collection'].update_one.call_args
        assert update_call[0][1]["$set"]["account_locked"] == True
        assert update_call[0][1]["$set"]["status"] == UserStatus.LOCKED.value


class TestUserProfile:
    """Test user profile operations"""
    
    @pytest.mark.asyncio
    async def test_get_user_profile(self, user_service, mock_dependencies, sample_user_data):
        """Test getting user profile"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = sample_user_data
        mock_dependencies['security_utils'].decrypt_sensitive_data.return_value = "Test User"
        
        # Execute
        profile = await user_service.get_user_profile("kratos_123")
        
        # Assertions
        assert isinstance(profile, UserProfile)
        assert profile.user_id == "kratos_123"
        assert profile.email == "test@example.com"
        assert profile.name == "Test User"
        assert profile.status == UserStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_user_profile_not_found(self, user_service, mock_dependencies):
        """Test getting profile for non-existent user"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = None
        
        # Execute and assert exception
        with pytest.raises(ValueError, match="User not found"):
            await user_service.get_user_profile("nonexistent_user")

    @pytest.mark.asyncio
    async def test_update_user_profile(self, user_service, mock_dependencies, sample_user_data):
        """Test updating user profile"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = sample_user_data
        mock_dependencies['users_collection'].update_one.return_value = MagicMock(matched_count=1)
        mock_dependencies['security_utils'].encrypt_sensitive_data.return_value = "encrypted_new_name"
        mock_dependencies['security_utils'].decrypt_sensitive_data.return_value = "New Name"
        
        # Execute update
        updates = {
            "name": "New Name",
            "preferences": {"theme": "dark"},
            "invalid_field": "should_be_ignored"
        }
        
        profile = await user_service.update_user_profile("kratos_123", updates)
        
        # Assertions
        assert isinstance(profile, UserProfile)
        mock_dependencies['users_collection'].update_one.assert_called()
        mock_dependencies['audit_service'].log_event.assert_called_with(
            "user_profile_updated",
            user_id="kratos_123",
            details={"updated_fields": ["name", "preferences"]}
        )

    @pytest.mark.asyncio
    async def test_update_user_profile_not_found(self, user_service, mock_dependencies):
        """Test updating profile for non-existent user"""
        # Setup mocks
        mock_dependencies['users_collection'].update_one.return_value = MagicMock(matched_count=0)
        
        # Execute and assert exception
        with pytest.raises(ValueError, match="User not found"):
            await user_service.update_user_profile("nonexistent_user", {"name": "New Name"})


class TestPasswordReset:
    """Test password reset functionality"""
    
    @pytest.mark.asyncio
    async def test_request_password_reset(self, user_service, mock_dependencies):
        """Test password reset request"""
        # Setup mocks
        mock_dependencies['redis_client'].exists.return_value = False  # No existing reset
        
        # Execute
        result = await user_service.request_password_reset("test@example.com", "127.0.0.1")
        
        # Assertions
        assert "message" in result
        assert "reset link has been sent" in result["message"]
        
        # Verify Redis operations
        mock_dependencies['redis_client'].setex.assert_called()
        mock_dependencies['email_service'].send_password_reset_email.assert_called()
        mock_dependencies['audit_service'].log_event.assert_called()

    @pytest.mark.asyncio
    async def test_password_reset_rate_limiting(self, user_service, mock_dependencies):
        """Test password reset rate limiting"""
        # Setup mocks - reset already requested
        mock_dependencies['redis_client'].exists.return_value = True
        
        # Execute and assert exception
        with pytest.raises(RateLimitExceededError):
            await user_service.request_password_reset("test@example.com", "127.0.0.1")


class TestEmailVerification:
    """Test email verification functionality"""
    
    @pytest.mark.asyncio
    async def test_verify_email_success(self, user_service, mock_dependencies, sample_user_data):
        """Test successful email verification"""
        # Setup mocks
        user_data = sample_user_data.copy()
        user_data["verification_token"] = "valid_token_123"
        user_data["is_verified"] = False
        user_data["status"] = UserStatus.PENDING_VERIFICATION.value
        
        mock_dependencies['users_collection'].find_one.return_value = user_data
        
        # Execute
        result = await user_service.verify_email("valid_token_123")
        
        # Assertions
        assert result["message"] == "Email verified successfully"
        
        # Verify database update
        mock_dependencies['users_collection'].update_one.assert_called()
        update_call = mock_dependencies['users_collection'].update_one.call_args
        assert update_call[0][1]["$set"]["is_verified"] == True
        assert update_call[0][1]["$set"]["status"] == UserStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, user_service, mock_dependencies):
        """Test email verification with invalid token"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = None
        
        # Execute and assert exception
        with pytest.raises(ValueError, match="Invalid verification token"):
            await user_service.verify_email("invalid_token")


class TestUserLogout:
    """Test user logout functionality"""
    
    @pytest.mark.asyncio
    async def test_logout_success(self, user_service, mock_dependencies):
        """Test successful logout"""
        # Setup mocks
        token_data = {"user_id": "kratos_123", "jti": "session_123"}
        mock_dependencies['security_utils'].validate_session_token.return_value = token_data
        
        # Execute
        result = await user_service.logout_user("valid_token", "127.0.0.1")
        
        # Assertions
        assert result["message"] == "Successfully logged out"
        
        # Verify session removal
        mock_dependencies['redis_client'].delete.assert_called_with("session:session_123")
        mock_dependencies['audit_service'].log_event.assert_called()

    @pytest.mark.asyncio
    async def test_logout_invalid_token(self, user_service, mock_dependencies):
        """Test logout with invalid token"""
        # Setup mocks
        mock_dependencies['security_utils'].validate_session_token.side_effect = Exception("Invalid token")
        
        # Execute and assert exception
        with pytest.raises(Exception):
            await user_service.logout_user("invalid_token", "127.0.0.1")


class TestAdminOperations:
    """Test admin operations"""
    
    @pytest.mark.asyncio
    async def test_lock_user_account(self, user_service, mock_dependencies):
        """Test locking user account"""
        # Setup mocks
        mock_dependencies['users_collection'].update_one.return_value = MagicMock(matched_count=1)
        mock_dependencies['redis_client'].keys.return_value = ["session:123"]
        mock_dependencies['redis_client'].get.return_value = b"kratos_123"
        
        # Execute
        result = await user_service.lock_user_account("kratos_123", "Suspicious activity", "admin_123")
        
        # Assertions
        assert result["message"] == "Account locked successfully"
        
        # Verify database update
        update_call = mock_dependencies['users_collection'].update_one.call_args
        assert update_call[0][1]["$set"]["account_locked"] == True
        assert update_call[0][1]["$set"]["status"] == UserStatus.LOCKED.value
        assert update_call[0][1]["$set"]["lock_reason"] == "Suspicious activity"
        
        # Verify session invalidation
        mock_dependencies['redis_client'].delete.assert_called()

    @pytest.mark.asyncio
    async def test_unlock_user_account(self, user_service, mock_dependencies):
        """Test unlocking user account"""
        # Setup mocks
        mock_dependencies['users_collection'].update_one.return_value = MagicMock(matched_count=1)
        
        # Execute
        result = await user_service.unlock_user_account("kratos_123", "admin_123")
        
        # Assertions
        assert result["message"] == "Account unlocked successfully"
        
        # Verify database update
        update_call = mock_dependencies['users_collection'].update_one.call_args
        assert update_call[0][1]["$set"]["account_locked"] == False
        assert update_call[0][1]["$set"]["status"] == UserStatus.ACTIVE.value
        assert update_call[0][1]["$set"]["failed_login_attempts"] == 0

    @pytest.mark.asyncio
    async def test_lock_account_user_not_found(self, user_service, mock_dependencies):
        """Test locking non-existent user account"""
        # Setup mocks
        mock_dependencies['users_collection'].update_one.return_value = MagicMock(matched_count=0)
        
        # Execute and assert exception
        with pytest.raises(ValueError, match="User not found"):
            await user_service.lock_user_account("nonexistent_user", "reason", "admin_123")

    @pytest.mark.asyncio
    async def test_get_user_activity(self, user_service, mock_dependencies):
        """Test getting user activity"""
        # Setup mocks
        activity_data = [{"event": "login", "timestamp": "2025-01-01T12:00:00Z"}]
        mock_dependencies['audit_service'].get_user_activity.return_value = activity_data
        
        # Execute
        result = await user_service.get_user_activity("kratos_123", 50)
        
        # Assertions
        assert result == activity_data
        mock_dependencies['audit_service'].get_user_activity.assert_called_with("kratos_123", 50)


class TestRateLimiting:
    """Test rate limiting functionality"""
    
    @pytest.mark.asyncio
    async def test_registration_rate_limiting_increment(self, user_service, mock_dependencies, valid_registration_request):
        """Test that registration rate limiting increments correctly"""
        # Setup mocks for successful registration
        mock_dependencies['users_collection'].find_one.return_value = None
        mock_dependencies['redis_client'].get.return_value = b'1'  # Under limit
        mock_dependencies['security_utils'].validate_password_strength.return_value = True
        mock_dependencies['security_utils'].encrypt_sensitive_data.return_value = "encrypted_name"
        mock_dependencies['kratos_service'].create_user.return_value = {"id": "kratos_123"}
        mock_dependencies['lago_service'].create_customer.return_value = {
            "customer": {"lago_id": "lago_123", "external_id": "test@example.com"}
        }
        mock_dependencies['users_collection'].insert_one.return_value = MagicMock(inserted_id="user_id_123")
        
        # Mock Redis pipeline
        pipeline_mock = MagicMock()
        mock_dependencies['redis_client'].pipeline.return_value = pipeline_mock
        
        # Execute
        await user_service.register_user(valid_registration_request, "127.0.0.1")
        
        # Verify rate limiting operations
        mock_dependencies['redis_client'].pipeline.assert_called()
        pipeline_mock.incr.assert_called()
        pipeline_mock.expire.assert_called()
        pipeline_mock.execute.assert_called()

    @pytest.mark.asyncio 
    async def test_login_rate_limiting_multiple_sources(self, user_service, mock_dependencies, valid_login_request):
        """Test login rate limiting from multiple sources"""
        # Setup mocks - both user and IP rate limiting
        mock_dependencies['redis_client'].get.side_effect = [b'2', b'10']  # User: 2, IP: 10 (over limit)
        
        # Execute and assert exception
        with pytest.raises(RateLimitExceededError, match="Too many login attempts from this IP"):
            await user_service.authenticate_user(valid_login_request)


class TestErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.mark.asyncio
    async def test_lago_service_retry_mechanism(self, user_service, mock_dependencies, valid_registration_request):
        """Test Lago service retry mechanism"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = None
        mock_dependencies['redis_client'].get.return_value = None
        mock_dependencies['security_utils'].validate_password_strength.return_value = True
        mock_dependencies['kratos_service'].create_user.return_value = {"id": "kratos_123"}
        
        # Mock Lago service to fail twice, then succeed
        mock_dependencies['lago_service'].create_customer.side_effect = [
            Exception("Service unavailable"),
            Exception("Service unavailable"),
            {"customer": {"lago_id": "lago_123", "external_id": "test@example.com"}}
        ]
        
        mock_dependencies['security_utils'].encrypt_sensitive_data.return_value = "encrypted_name"
        mock_dependencies['users_collection'].insert_one.return_value = MagicMock(inserted_id="user_id_123")
        
        # Execute - should succeed after retries
        result = await user_service.register_user(valid_registration_request, "127.0.0.1")
        
        # Verify retries occurred
        assert mock_dependencies['lago_service'].create_customer.call_count == 3
        assert result["user_id"] == "kratos_123"

    @pytest.mark.asyncio
    async def test_lago_service_max_retries_exceeded(self, user_service, mock_dependencies, valid_registration_request):
        """Test Lago service max retries exceeded"""
        # Setup mocks
        mock_dependencies['users_collection'].find_one.return_value = None
        mock_dependencies['redis_client'].get.return_value = None
        mock_dependencies['security_utils'].validate_password_strength.return_value = True
        mock_dependencies['kratos_service'].create_user.return_value = {"id": "kratos_123"}
        
        # Mock Lago service to always fail
        mock_dependencies['lago_service'].create_customer.side_effect = Exception("Service unavailable")
        
        # Execute and assert exception
        with pytest.raises(ServiceUnavailableError):
            await user_service.register_user(valid_registration_request, "127.0.0.1")
        
        # Verify max retries attempted
        assert mock_dependencies['lago_service'].create_customer.call_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])