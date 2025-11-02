# tests/test_multitenant.py - Comprehensive multi-tenant tests

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from bson import ObjectId

from services.tenant_service import TenantService, TenantStatus, SubscriptionPlan, TenantUserRole
from main import app

class TestTenantService:
    """Test TenantService functionality"""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for TenantService"""
        return {
            'tenants_collection': MagicMock(),
            'tenant_users_collection': MagicMock(),
            'tenant_invitations_collection': MagicMock(),
            'users_collection': MagicMock(),
            'audit_service': AsyncMock(),
            'email_service': AsyncMock()
        }
    
    @pytest.fixture
    def tenant_service(self, mock_dependencies):
        """Create TenantService instance with mocked dependencies"""
        return TenantService(**mock_dependencies)
    
    @pytest.fixture
    def sample_tenant_data(self):
        """Sample tenant data"""
        return {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "name": "Test Company",
            "subdomain": "testcompany",
            "domain": None,
            "status": "active",
            "subscription_plan": "trial",
            "settings": {
                "branding": {"primary_color": "#3b82f6"},
                "features": {"sso_enabled": False},
                "limits": {"max_users": 5}
            },
            "created_at": "2025-01-01T12:00:00Z",
            "trial_ends_at": "2025-02-01T12:00:00Z"
        }

    @pytest.mark.asyncio
    async def test_create_tenant_success(self, tenant_service, mock_dependencies):
        """Test successful tenant creation"""
        # Setup mocks
        mock_dependencies['tenants_collection'].find_one.return_value = None  # No existing tenant
        mock_dependencies['tenants_collection'].insert_one.return_value = MagicMock(
            inserted_id=ObjectId("507f1f77bcf86cd799439011")
        )
        mock_dependencies['users_collection'].find_one.return_value = {"primary_tenant_id": None}
        
        # Execute
        result = await tenant_service.create_tenant(
            creator_user_id="user_123",
            name="Test Company",
            subdomain="testcompany"
        )
        
        # Assertions
        assert result["name"] == "Test Company"
        assert result["subdomain"] == "testcompany"
        assert result["status"] == "trial"
        assert "tenant_id" in result
        
        # Verify calls
        mock_dependencies['tenants_collection'].insert_one.assert_called_once()
        mock_dependencies['tenant_users_collection'].insert_one.assert_called_once()
        mock_dependencies['audit_service'].log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_tenant_duplicate_subdomain(self, tenant_service, mock_dependencies):
        """Test tenant creation with duplicate subdomain"""
        # Setup mocks - subdomain already exists
        mock_dependencies['tenants_collection'].find_one.return_value = {"subdomain": "testcompany"}
        
        # Execute and assert exception
        with pytest.raises(ValueError, match="Subdomain already exists"):
            await tenant_service.create_tenant(
                creator_user_id="user_123",
                name="Test Company",
                subdomain="testcompany"
            )

    @pytest.mark.asyncio
    async def test_get_tenant_by_subdomain(self, tenant_service, mock_dependencies, sample_tenant_data):
        """Test getting tenant by subdomain"""
        # Setup mocks
        mock_dependencies['tenants_collection'].find_one.return_value = sample_tenant_data
        mock_dependencies['tenant_users_collection'].count_documents.return_value = 3  # user count
        
        # Execute
        tenant = await tenant_service.get_tenant_by_subdomain("testcompany")
        
        # Assertions
        assert tenant is not None
        assert tenant.name == "Test Company"
        assert tenant.subdomain == "testcompany"
        assert tenant.status == TenantStatus.ACTIVE
        assert tenant.user_count == 3

    @pytest.mark.asyncio
    async def test_get_user_tenants(self, tenant_service, mock_dependencies, sample_tenant_data):
        """Test getting all tenants for a user"""
        # Setup mocks
        mock_dependencies['tenant_users_collection'].find.return_value = [
            {
                "tenant_id": ObjectId("507f1f77bcf86cd799439011"),
                "user_id": "user_123",
                "role": "owner",
                "status": "active",
                "permissions": ["tenants:read"],
                "joined_at": "2025-01-01T12:00:00Z"
            }
        ]
        
        # Mock get_tenant_by_id
        with patch.object(tenant_service, 'get_tenant_by_id') as mock_get_tenant:
            mock_tenant = MagicMock()
            mock_tenant.name = "Test Company"
            mock_tenant.subdomain = "testcompany"
            mock_get_tenant.return_value = mock_tenant
            
            # Execute
            result = await tenant_service.get_user_tenants("user_123")
            
            # Assertions
            assert len(result) == 1
            assert result[0]["role"] == "owner"
            assert result[0]["tenant"] == mock_tenant

    @pytest.mark.asyncio
    async def test_invite_user_to_tenant(self, tenant_service, mock_dependencies):
        """Test inviting user to tenant"""
        # Setup mocks
        mock_dependencies['tenant_users_collection'].find_one.return_value = None  # Not already member
        mock_dependencies['tenant_invitations_collection'].find_one.return_value = None  # No existing invitation
        mock_dependencies['tenant_invitations_collection'].insert_one.return_value = MagicMock(
            inserted_id=ObjectId("507f1f77bcf86cd799439012")
        )
        
        # Mock permission check
        with patch.object(tenant_service, '_user_can_manage_users', return_value=True):
            with patch.object(tenant_service, 'get_tenant_by_id') as mock_get_tenant:
                mock_tenant = MagicMock()
                mock_tenant.name = "Test Company"
                mock_get_tenant.return_value = mock_tenant
                
                mock_dependencies['users_collection'].find_one.return_value = {"name": "Inviter"}
                
                # Execute
                result = await tenant_service.invite_user_to_tenant(
                    inviter_user_id="user_123",
                    tenant_id="507f1f77bcf86cd799439011",
                    email="newuser@example.com",
                    role="user"
                )
                
                # Assertions
                assert "Invitation sent successfully" in result["message"]
                assert "invitation_id" in result
                
                # Verify calls
                mock_dependencies['tenant_invitations_collection'].insert_one.assert_called_once()
                mock_dependencies['email_service'].send_tenant_invitation_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_accept_tenant_invitation(self, tenant_service, mock_dependencies):
        """Test accepting tenant invitation"""
        # Setup mocks
        invitation_data = {
            "_id": ObjectId("507f1f77bcf86cd799439012"),
            "tenant_id": ObjectId("507f1f77bcf86cd799439011"),
            "email": "newuser@example.com",
            "role": "user",
            "token": "invitation_token_123",
            "invited_by": "inviter_123",
            "status": "pending",
            "expires_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "permissions": ["tenants:read"]
        }
        
        mock_dependencies['tenant_invitations_collection'].find_one.return_value = invitation_data
        mock_dependencies['users_collection'].find_one.return_value = {
            "kratos_id": "user_123",
            "email": "newuser@example.com",
            "primary_tenant_id": None
        }
        
        # Mock get_tenant_by_id
        with patch.object(tenant_service, 'get_tenant_by_id') as mock_get_tenant:
            mock_tenant = MagicMock()
            mock_tenant.name = "Test Company"
            mock_tenant.subdomain = "testcompany"
            mock_get_tenant.return_value = mock_tenant
            
            # Execute
            result = await tenant_service.accept_tenant_invitation(
                user_id="user_123",
                invitation_token="invitation_token_123"
            )
            
            # Assertions
            assert "Successfully joined tenant" in result["message"]
            assert result["tenant"]["name"] == "Test Company"
            assert result["role"] == "user"
            
            # Verify calls
            mock_dependencies['tenant_users_collection'].insert_one.assert_called_once()
            mock_dependencies['tenant_invitations_collection'].update_one.assert_called()

    @pytest.mark.asyncio
    async def test_switch_user_tenant(self, tenant_service, mock_dependencies):
        """Test switching user's active tenant"""
        # Setup mocks
        mock_dependencies['tenant_users_collection'].find_one.return_value = {
            "tenant_id": ObjectId("507f1f77bcf86cd799439011"),
            "user_id": "user_123",
            "role": "admin",
            "status": "active",
            "permissions": ["tenants:read", "tenants:manage_users"]
        }
        
        # Mock get_tenant_by_id
        with patch.object(tenant_service, 'get_tenant_by_id') as mock_get_tenant:
            mock_tenant = MagicMock()
            mock_tenant.name = "Test Company"
            mock_tenant.subdomain = "testcompany"
            mock_get_tenant.return_value = mock_tenant
            
            # Execute
            result = await tenant_service.switch_user_tenant(
                user_id="user_123",
                tenant_id="507f1f77bcf86cd799439011"
            )
            
            # Assertions
            assert "Successfully switched tenant" in result["message"]
            assert result["tenant"]["name"] == "Test Company"
            assert result["role"] == "admin"
            
            # Verify primary tenant was updated
            mock_dependencies['users_collection'].update_one.assert_called_with(
                {"kratos_id": "user_123"},
                {"$set": {"primary_tenant_id": ObjectId("507f1f77bcf86cd799439011")}}
            )

    @pytest.mark.asyncio
    async def test_remove_user_from_tenant(self, tenant_service, mock_dependencies):
        """Test removing user from tenant"""
        # Setup mocks - user is admin, not owner
        mock_dependencies['tenant_users_collection'].find_one.return_value = {
            "tenant_id": ObjectId("507f1f77bcf86cd799439011"),
            "user_id": "target_user",
            "role": "admin"
        }
        
        mock_dependencies['tenant_users_collection'].delete_one.return_value = MagicMock(deleted_count=1)
        mock_dependencies['users_collection'].find_one.return_value = {"primary_tenant_id": None}
        
        # Mock permission check
        with patch.object(tenant_service, '_user_can_manage_users', return_value=True):
            # Execute
            result = await tenant_service.remove_user_from_tenant(
                admin_user_id="admin_123",
                tenant_id="507f1f77bcf86cd799439011",
                target_user_id="target_user"
            )
            
            # Assertions
            assert "User removed from tenant successfully" in result["message"]
            
            # Verify deletion
            mock_dependencies['tenant_users_collection'].delete_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_last_owner_forbidden(self, tenant_service, mock_dependencies):
        """Test that removing the last owner is forbidden"""
        # Setup mocks - user is owner and only owner
        mock_dependencies['tenant_users_collection'].find_one.return_value = {
            "tenant_id": ObjectId("507f1f77bcf86cd799439011"),
            "user_id": "owner_user",
            "role": "owner"
        }
        
        mock_dependencies['tenant_users_collection'].count_documents.return_value = 0  # No other owners
        
        # Mock permission check
        with patch.object(tenant_service, '_user_can_manage_users', return_value=True):
            # Execute and assert exception
            with pytest.raises(ValueError, match="Cannot remove the last owner"):
                await tenant_service.remove_user_from_tenant(
                    admin_user_id="admin_123",
                    tenant_id="507f1f77bcf86cd799439011",
                    target_user_id="owner_user"
                )


class TestMultiTenantAPI:
    """Test multi-tenant API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_tenant_service(self):
        """Mock TenantService"""
        return AsyncMock(spec=TenantService)
    
    @pytest.fixture
    def mock_app_dependencies(self, mock_tenant_service):
        """Mock app dependencies"""
        with patch.object(app.state, 'tenant_service', mock_tenant_service), \
             patch.object(app.state, 'user_service', AsyncMock()), \
             patch.object(app.state, 'security_utils', MagicMock()), \
             patch.object(app.state, '