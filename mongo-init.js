// Complete mongo-init.js - Multi-tenant Authentication System with RBAC and Auto-promotion

print("🚀 Initializing Complete Multi-tenant Authentication System...");

db = db.getSiblingDB("fq_db");

// =====================================
// USERS COLLECTION - Enhanced for multi-tenancy
// =====================================
db.createCollection("users", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["email", "kratos_id", "created_at"],
      properties: {
        email: {
          bsonType: "string",
          pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
          description: "Valid email address",
        },
        kratos_id: {
          bsonType: "string",
          description: "Kratos identity ID",
        },
        lago_customer_id: {
          bsonType: ["string", "null"],
          description: "Lago billing customer ID",
        },
        external_id: {
          bsonType: ["string", "null"],
          description: "External system ID",
        },
        name: {
          bsonType: "string",
          description: "Encrypted user name",
        },
        global_role: {
          bsonType: "string",
          enum: ["user", "admin", "superadmin", "system"],
          description: "Global role across all tenants",
        },
        primary_tenant_id: {
          bsonType: ["objectId", "null"],
          description: "Primary/default tenant for this user",
        },
        is_system_user: {
          bsonType: "bool",
          description: "Whether this is a system/service account",
        },
        global_permissions: {
          bsonType: "array",
          items: { bsonType: "string" },
          description: "Global system permissions",
        },
        created_at: { bsonType: "string" },
        updated_at: { bsonType: ["string", "null"] },
        last_login: { bsonType: ["string", "null"] },
        last_login_ip: { bsonType: ["string", "null"] },
        failed_login_attempts: { bsonType: "int", minimum: 0 },
        account_locked: { bsonType: "bool" },
        locked_at: { bsonType: ["string", "null"] },
        locked_by: { bsonType: ["string", "null"] },
        lock_reason: { bsonType: ["string", "null"] },
        terms_accepted: { bsonType: "bool" },
        marketing_consent: { bsonType: "bool" },
        registration_ip: { bsonType: "string" },
        status: {
          bsonType: "string",
          enum: [
            "active",
            "inactive",
            "locked",
            "suspended",
            "pending_verification",
          ],
          description: "Account status",
        },
        is_verified: { bsonType: "bool" },
        verification_token: { bsonType: ["string", "null"] },
        password_reset_token: { bsonType: ["string", "null"] },
        password_reset_expires: { bsonType: ["string", "null"] },
        preferences: {
          bsonType: "object",
          description: "User preferences and settings",
        },
        referral_code: { bsonType: ["string", "null"] },
        referred_by: { bsonType: ["string", "null"] },
        referral_count: { bsonType: ["int", "null"], minimum: 0 },
      },
    },
  },
});

// =====================================
// TENANTS COLLECTION
// =====================================
db.createCollection("tenants", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["name", "subdomain", "status", "created_at"],
      properties: {
        name: {
          bsonType: "string",
          minLength: 2,
          maxLength: 100,
          description: "Tenant display name",
        },
        subdomain: {
          bsonType: "string",
          pattern: "^[a-z0-9][a-z0-9-]*[a-z0-9]$",
          minLength: 3,
          maxLength: 63,
          description: "Unique subdomain identifier",
        },
        domain: {
          bsonType: ["string", "null"],
          description: "Custom domain (optional)",
        },
        status: {
          bsonType: "string",
          enum: ["active", "inactive", "suspended", "trial", "pending_setup"],
          description: "Tenant status",
        },
        subscription_plan: {
          bsonType: "string",
          enum: ["trial", "basic", "professional", "enterprise"],
          description: "Subscription plan level",
        },
        settings: {
          bsonType: "object",
          properties: {
            branding: {
              bsonType: "object",
              properties: {
                logo_url: { bsonType: ["string", "null"] },
                favicon_url: { bsonType: ["string", "null"] },
                primary_color: { bsonType: ["string", "null"] },
                secondary_color: { bsonType: ["string", "null"] },
                accent_color: { bsonType: ["string", "null"] },
                custom_css: { bsonType: ["string", "null"] },
                company_name: { bsonType: ["string", "null"] },
              },
            },
            features: {
              bsonType: "object",
              properties: {
                sso_enabled: { bsonType: "bool" },
                mfa_required: { bsonType: "bool" },
                api_access: { bsonType: "bool" },
                audit_logs: { bsonType: "bool" },
                custom_roles: { bsonType: "bool" },
                white_label: { bsonType: "bool" },
                advanced_analytics: { bsonType: "bool" },
                webhook_support: { bsonType: "bool" },
                integrations: { bsonType: "array" },
              },
            },
            limits: {
              bsonType: "object",
              properties: {
                max_users: { bsonType: ["int", "null"] },
                max_admins: { bsonType: ["int", "null"] },
                storage_gb: { bsonType: ["int", "null"] },
                api_calls_per_month: { bsonType: ["int", "null"] },
                max_integrations: { bsonType: ["int", "null"] },
                max_webhooks: { bsonType: ["int", "null"] },
              },
            },
            security: {
              bsonType: "object",
              properties: {
                password_policy: { bsonType: "object" },
                session_timeout: { bsonType: ["int", "null"] },
                ip_whitelist: { bsonType: ["array", "null"] },
                allowed_domains: { bsonType: ["array", "null"] },
                require_mfa: { bsonType: "bool" },
                login_attempts_limit: { bsonType: "int" },
              },
            },
            notifications: {
              bsonType: "object",
              properties: {
                email_notifications: { bsonType: "bool" },
                slack_webhook: { bsonType: ["string", "null"] },
                teams_webhook: { bsonType: ["string", "null"] },
              },
            },
          },
        },
        billing_info: {
          bsonType: "object",
          properties: {
            lago_customer_id: { bsonType: ["string", "null"] },
            stripe_customer_id: { bsonType: ["string", "null"] },
            billing_email: { bsonType: ["string", "null"] },
            billing_address: { bsonType: ["object", "null"] },
            payment_method_id: { bsonType: ["string", "null"] },
            next_billing_date: { bsonType: ["string", "null"] },
          },
        },
        created_at: { bsonType: "string" },
        updated_at: { bsonType: ["string", "null"] },
        created_by: { bsonType: ["string", "null"] },
        trial_starts_at: { bsonType: ["string", "null"] },
        trial_ends_at: { bsonType: ["string", "null"] },
        suspended_at: { bsonType: ["string", "null"] },
        suspended_by: { bsonType: ["string", "null"] },
        suspension_reason: { bsonType: ["string", "null"] },
        last_activity: { bsonType: ["string", "null"] },
        metadata: { bsonType: ["object", "null"] },
      },
    },
  },
});

// =====================================
// TENANT USERS - Junction table for user-tenant relationships
// =====================================
db.createCollection("tenant_users", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenant_id", "user_id", "role", "status", "created_at"],
      properties: {
        tenant_id: {
          bsonType: "objectId",
          description: "Reference to tenant",
        },
        user_id: {
          bsonType: "string",
          description: "Kratos user ID",
        },
        role: {
          bsonType: "string",
          enum: ["owner", "admin", "user", "guest", "billing_admin", "support"],
          description: "User role within this tenant",
        },
        status: {
          bsonType: "string",
          enum: ["active", "inactive", "invited", "suspended"],
          description: "User status within this tenant",
        },
        permissions: {
          bsonType: "array",
          items: { bsonType: "string" },
          description: "Additional permissions for this tenant",
        },
        custom_role_id: {
          bsonType: ["objectId", "null"],
          description: "Custom role assigned to user in this tenant",
        },
        invited_by: {
          bsonType: ["string", "null"],
          description: "User ID who sent the invitation",
        },
        invited_at: {
          bsonType: ["string", "null"],
          description: "When the invitation was sent",
        },
        joined_at: {
          bsonType: ["string", "null"],
          description: "When the user joined the tenant",
        },
        last_accessed: {
          bsonType: ["string", "null"],
          description: "Last time user accessed this tenant",
        },
        access_granted_by: {
          bsonType: ["string", "null"],
          description: "Admin who granted access",
        },
        created_at: { bsonType: "string" },
        updated_at: { bsonType: ["string", "null"] },
      },
    },
  },
});

// =====================================
// TENANT INVITATIONS
// =====================================
db.createCollection("tenant_invitations", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "tenant_id",
        "email",
        "role",
        "token",
        "invited_by",
        "created_at",
        "expires_at",
      ],
      properties: {
        tenant_id: { bsonType: "objectId" },
        email: {
          bsonType: "string",
          pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
        },
        role: {
          bsonType: "string",
          enum: ["admin", "user", "guest", "billing_admin", "support"],
        },
        permissions: {
          bsonType: "array",
          items: { bsonType: "string" },
        },
        custom_role_id: {
          bsonType: ["objectId", "null"],
          description: "Custom role to assign",
        },
        token: {
          bsonType: "string",
          description: "Unique invitation token",
        },
        invited_by: {
          bsonType: "string",
          description: "User ID who sent the invitation",
        },
        message: {
          bsonType: ["string", "null"],
          description: "Optional invitation message",
        },
        status: {
          bsonType: "string",
          enum: ["pending", "accepted", "rejected", "expired", "cancelled"],
          description: "Invitation status",
        },
        created_at: { bsonType: "string" },
        expires_at: { bsonType: "string" },
        accepted_at: { bsonType: ["string", "null"] },
        rejected_at: { bsonType: ["string", "null"] },
        cancelled_at: { bsonType: ["string", "null"] },
        cancelled_by: { bsonType: ["string", "null"] },
      },
    },
  },
});

// =====================================
// ROLES COLLECTION - Enhanced for RBAC
// =====================================
db.createCollection("roles", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["name", "permissions", "created_at"],
      properties: {
        name: {
          bsonType: "string",
          description: "Role name/identifier",
        },
        display_name: { bsonType: "string" },
        description: { bsonType: "string" },
        type: {
          bsonType: "string",
          enum: ["system", "custom", "tenant_specific"],
          description: "Type of role",
        },
        tenant_id: {
          bsonType: ["objectId", "null"],
          description: "Tenant ID for tenant-specific roles",
        },
        permissions: {
          bsonType: "array",
          items: { bsonType: "string" },
        },
        inherits_from: {
          bsonType: ["array", "null"],
          items: { bsonType: "objectId" },
          description: "Parent roles this role inherits from",
        },
        is_system_role: { bsonType: "bool" },
        is_default: { bsonType: "bool" },
        created_at: { bsonType: "string" },
        updated_at: { bsonType: ["string", "null"] },
        created_by: { bsonType: ["string", "null"] },
        metadata: { bsonType: ["object", "null"] },
      },
    },
  },
});

// =====================================
// PERMISSIONS COLLECTION
// =====================================
db.createCollection("permissions", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["name", "resource", "action"],
      properties: {
        name: {
          bsonType: "string",
          description: "Permission identifier (e.g., users:read)",
        },
        resource: {
          bsonType: "string",
          description: "Resource type (users, tenants, etc.)",
        },
        action: {
          bsonType: "string",
          description: "Action (read, write, delete, etc.)",
        },
        description: { bsonType: "string" },
        category: {
          bsonType: "string",
          description: "Permission category for grouping",
        },
        is_system_permission: { bsonType: "bool" },
        created_at: { bsonType: "string" },
      },
    },
  },
});

// =====================================
// AUDIT LOGS - Enhanced with tenant context
// =====================================
db.createCollection("audit_logs", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["timestamp", "event_type", "severity"],
      properties: {
        timestamp: { bsonType: "string" },
        event_type: { bsonType: "string" },
        tenant_id: { bsonType: ["objectId", "null"] },
        user_id: { bsonType: ["string", "null"] },
        target_user_id: { bsonType: ["string", "null"] },
        admin_user_id: { bsonType: ["string", "null"] },
        ip_address: { bsonType: ["string", "null"] },
        user_agent: { bsonType: ["string", "null"] },
        details: { bsonType: "object" },
        severity: {
          bsonType: "string",
          enum: ["info", "warning", "error", "critical"],
        },
        session_id: { bsonType: ["string", "null"] },
        action: { bsonType: ["string", "null"] },
        resource: { bsonType: ["string", "null"] },
        before_state: { bsonType: ["object", "null"] },
        after_state: { bsonType: ["object", "null"] },
        correlation_id: { bsonType: ["string", "null"] },
      },
    },
  },
});

// =====================================
// SESSIONS COLLECTION - Enhanced session tracking
// =====================================
db.createCollection("sessions", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["session_id", "user_id", "created_at"],
      properties: {
        session_id: {
          bsonType: "string",
          description: "Unique session identifier",
        },
        user_id: {
          bsonType: "string",
          description: "Associated user ID",
        },
        tenant_id: {
          bsonType: ["objectId", "null"],
          description: "Active tenant for this session",
        },
        ip_address: {
          bsonType: ["string", "null"],
          description: "Session IP address",
        },
        user_agent: {
          bsonType: ["string", "null"],
          description: "User agent string",
        },
        device_fingerprint: {
          bsonType: ["string", "null"],
          description: "Device fingerprint",
        },
        created_at: {
          bsonType: "string",
          description: "Session creation time",
        },
        last_activity: {
          bsonType: "string",
          description: "Last session activity",
        },
        expires_at: {
          bsonType: "string",
          description: "Session expiration time",
        },
        is_active: {
          bsonType: "bool",
          description: "Whether session is active",
        },
        remember_me: {
          bsonType: "bool",
          description: "Long-lived session flag",
        },
        metadata: { bsonType: ["object", "null"] },
      },
    },
  },
});

// =====================================
// WEBHOOKS COLLECTION
// =====================================
db.createCollection("webhooks", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenant_id", "url", "events", "status", "created_at"],
      properties: {
        tenant_id: { bsonType: "objectId" },
        name: { bsonType: "string" },
        url: { bsonType: "string" },
        secret: { bsonType: "string" },
        events: {
          bsonType: "array",
          items: { bsonType: "string" },
        },
        status: {
          bsonType: "string",
          enum: ["active", "inactive", "failed"],
        },
        last_triggered: { bsonType: ["string", "null"] },
        failure_count: { bsonType: "int", minimum: 0 },
        created_at: { bsonType: "string" },
        updated_at: { bsonType: ["string", "null"] },
        created_by: { bsonType: "string" },
      },
    },
  },
});

// =====================================
// INTEGRATIONS COLLECTION
// =====================================
db.createCollection("integrations", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenant_id", "type", "name", "status", "created_at"],
      properties: {
        tenant_id: { bsonType: "objectId" },
        type: {
          bsonType: "string",
          enum: ["slack", "teams", "github", "jira", "custom"],
        },
        name: { bsonType: "string" },
        description: { bsonType: ["string", "null"] },
        config: { bsonType: "object" },
        credentials: { bsonType: "object" },
        status: {
          bsonType: "string",
          enum: ["active", "inactive", "error", "setup"],
        },
        last_sync: { bsonType: ["string", "null"] },
        error_message: { bsonType: ["string", "null"] },
        created_at: { bsonType: "string" },
        updated_at: { bsonType: ["string", "null"] },
        created_by: { bsonType: "string" },
      },
    },
  },
});

// =====================================
// SYSTEM CONFIG COLLECTION
// =====================================
db.createCollection("system_config", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["key", "value"],
      properties: {
        key: { bsonType: "string" },
        value: {
          bsonType: ["string", "bool", "int", "double", "object", "array"],
        },
        description: { bsonType: "string" },
        category: { bsonType: "string" },
        is_sensitive: { bsonType: "bool" },
        created_at: { bsonType: "string" },
        updated_at: { bsonType: ["string", "null"] },
        updated_by: { bsonType: ["string", "null"] },
      },
    },
  },
});

print("📊 Creating comprehensive indexes...");

// USERS INDEXES
db.users.createIndex({ email: 1 }, { unique: true });
db.users.createIndex({ kratos_id: 1 }, { unique: true });
db.users.createIndex({ lago_customer_id: 1 });
db.users.createIndex({ created_at: 1 });
db.users.createIndex({ account_locked: 1 });
db.users.createIndex({ global_role: 1 });
db.users.createIndex({ status: 1 });
db.users.createIndex({ is_verified: 1 });
db.users.createIndex({ primary_tenant_id: 1 });
db.users.createIndex({ is_system_user: 1 });
db.users.createIndex({ verification_token: 1 }, { sparse: true });
db.users.createIndex({ password_reset_token: 1 }, { sparse: true });
db.users.createIndex({ referral_code: 1 }, { sparse: true });
db.users.createIndex({ global_role: 1, status: 1 });

// TENANTS INDEXES
db.tenants.createIndex({ subdomain: 1 }, { unique: true });
db.tenants.createIndex({ domain: 1 }, { unique: true, sparse: true });
db.tenants.createIndex({ status: 1 });
db.tenants.createIndex({ subscription_plan: 1 });
db.tenants.createIndex({ created_at: 1 });
db.tenants.createIndex({ trial_ends_at: 1 }, { sparse: true });
db.tenants.createIndex({ created_by: 1 });
db.tenants.createIndex({ status: 1, subscription_plan: 1 });

// TENANT USERS INDEXES
db.tenant_users.createIndex({ tenant_id: 1, user_id: 1 }, { unique: true });
db.tenant_users.createIndex({ tenant_id: 1, role: 1 });
db.tenant_users.createIndex({ user_id: 1 });
db.tenant_users.createIndex({ status: 1 });
db.tenant_users.createIndex({ tenant_id: 1, status: 1 });
db.tenant_users.createIndex({ tenant_id: 1, role: 1, status: 1 });

// TENANT INVITATIONS INDEXES
db.tenant_invitations.createIndex({ tenant_id: 1 });
db.tenant_invitations.createIndex({ email: 1 });
db.tenant_invitations.createIndex({ token: 1 }, { unique: true });
db.tenant_invitations.createIndex({ status: 1 });
db.tenant_invitations.createIndex({ invited_by: 1 });

try {
  // Drop existing expires_at index if it exists without TTL
  try {
    db.tenant_invitations.dropIndex("expires_at_1");
  } catch (e) {
    // Index might not exist, continue
  }

  // Create TTL index for invitation cleanup
  db.tenant_invitations.createIndex(
    { expires_at: 1 },
    { expireAfterSeconds: 0 }
  );
} catch (e) {
  print(
    "Warning: Could not create TTL index on tenant_invitations.expires_at:",
    e.message
  );
}

// ROLES INDEXES
db.roles.createIndex({ name: 1, tenant_id: 1 }, { unique: true });
db.roles.createIndex({ type: 1 });
db.roles.createIndex({ tenant_id: 1 });
db.roles.createIndex({ is_system_role: 1 });
db.roles.createIndex({ created_by: 1 });

// PERMISSIONS INDEXES
db.permissions.createIndex({ name: 1 }, { unique: true });
db.permissions.createIndex({ resource: 1, action: 1 });
db.permissions.createIndex({ category: 1 });
db.permissions.createIndex({ is_system_permission: 1 });

// AUDIT LOGS INDEXES
try {
  // Drop existing timestamp index if it exists without TTL
  try {
    db.audit_logs.dropIndex("timestamp_1");
  } catch (e) {
    // Index might not exist, continue
  }

  // Create TTL index for audit log cleanup (90 days)
  db.audit_logs.createIndex({ timestamp: 1 }, { expireAfterSeconds: 7776000 });
} catch (e) {
  print(
    "Warning: Could not create TTL index on audit_logs.timestamp:",
    e.message
  );
}

db.audit_logs.createIndex({ event_type: 1 });
db.audit_logs.createIndex({ tenant_id: 1, timestamp: -1 });
db.audit_logs.createIndex({ user_id: 1, timestamp: -1 });
db.audit_logs.createIndex({ target_user_id: 1 });
db.audit_logs.createIndex({ admin_user_id: 1 });
db.audit_logs.createIndex({ severity: 1 });
db.audit_logs.createIndex({ ip_address: 1 });
db.audit_logs.createIndex({ correlation_id: 1 });

// SESSIONS INDEXES
try {
  // Drop existing expires_at index if it exists without TTL
  try {
    db.sessions.dropIndex("expires_at_1");
  } catch (e) {
    // Index might not exist, continue
  }

  // Create TTL index for session cleanup
  db.sessions.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 });
} catch (e) {
  print(
    "Warning: Could not create TTL index on sessions.expires_at:",
    e.message
  );
}

db.sessions.createIndex({ session_id: 1 }, { unique: true });
db.sessions.createIndex({ user_id: 1 });
db.sessions.createIndex({ tenant_id: 1 });
db.sessions.createIndex({ is_active: 1, last_activity: -1 });

// WEBHOOKS INDEXES
db.webhooks.createIndex({ tenant_id: 1 });
db.webhooks.createIndex({ status: 1 });
db.webhooks.createIndex({ created_by: 1 });

// INTEGRATIONS INDEXES
db.integrations.createIndex({ tenant_id: 1, type: 1 });
db.integrations.createIndex({ status: 1 });
db.integrations.createIndex({ created_by: 1 });

// SYSTEM CONFIG INDEXES
db.system_config.createIndex({ key: 1 }, { unique: true });
db.system_config.createIndex({ category: 1 });

print("🔐 Setting up comprehensive permissions system...");

// SYSTEM PERMISSIONS
const permissions = [
  // User management permissions
  {
    name: "users:read",
    resource: "users",
    action: "read",
    description: "View user profiles",
    category: "user_management",
    is_system_permission: true,
  },
  {
    name: "users:write",
    resource: "users",
    action: "write",
    description: "Create and update users",
    category: "user_management",
    is_system_permission: true,
  },
  {
    name: "users:delete",
    resource: "users",
    action: "delete",
    description: "Delete users",
    category: "user_management",
    is_system_permission: true,
  },
  {
    name: "users:lock",
    resource: "users",
    action: "lock",
    description: "Lock/unlock user accounts",
    category: "user_management",
    is_system_permission: true,
  },
  {
    name: "users:impersonate",
    resource: "users",
    action: "impersonate",
    description: "Login as another user",
    category: "user_management",
    is_system_permission: true,
  },

  // Tenant management permissions
  {
    name: "tenants:read",
    resource: "tenants",
    action: "read",
    description: "View tenant information",
    category: "tenant_management",
    is_system_permission: true,
  },
  {
    name: "tenants:write",
    resource: "tenants",
    action: "write",
    description: "Create and update tenants",
    category: "tenant_management",
    is_system_permission: true,
  },
  {
    name: "tenants:delete",
    resource: "tenants",
    action: "delete",
    description: "Delete tenants",
    category: "tenant_management",
    is_system_permission: true,
  },
  {
    name: "tenants:manage_users",
    resource: "tenants",
    action: "manage_users",
    description: "Manage tenant users",
    category: "tenant_management",
    is_system_permission: true,
  },
  {
    name: "tenants:manage_settings",
    resource: "tenants",
    action: "manage_settings",
    description: "Manage tenant settings",
    category: "tenant_management",
    is_system_permission: true,
  },
  {
    name: "tenants:billing",
    resource: "tenants",
    action: "billing",
    description: "Manage tenant billing",
    category: "tenant_management",
    is_system_permission: true,
  },
  {
    name: "tenants:invite_users",
    resource: "tenants",
    action: "invite_users",
    description: "Invite users to tenant",
    category: "tenant_management",
    is_system_permission: true,
  },
  {
    name: "tenants:switch",
    resource: "tenants",
    action: "switch",
    description: "Switch between tenants",
    category: "tenant_management",
    is_system_permission: true,
  },

  // Role and permission management
  {
    name: "roles:read",
    resource: "roles",
    action: "read",
    description: "View roles",
    category: "rbac",
    is_system_permission: true,
  },
  {
    name: "roles:write",
    resource: "roles",
    action: "write",
    description: "Create and update roles",
    category: "rbac",
    is_system_permission: true,
  },
  {
    name: "roles:delete",
    resource: "roles",
    action: "delete",
    description: "Delete roles",
    category: "rbac",
    is_system_permission: true,
  },
  {
    name: "roles:assign",
    resource: "roles",
    action: "assign",
    description: "Assign roles to users",
    category: "rbac",
    is_system_permission: true,
  },

  // Audit and security
  {
    name: "audit:read",
    resource: "audit",
    action: "read",
    description: "View audit logs",
    category: "security",
    is_system_permission: true,
  },
  {
    name: "audit:export",
    resource: "audit",
    action: "export",
    description: "Export audit logs",
    category: "security",
    is_system_permission: true,
  },

  // Webhooks
  {
    name: "webhooks:read",
    resource: "webhooks",
    action: "read",
    description: "View webhooks",
    category: "integrations",
    is_system_permission: true,
  },
  {
    name: "webhooks:write",
    resource: "webhooks",
    action: "write",
    description: "Create and update webhooks",
    category: "integrations",
    is_system_permission: true,
  },
  {
    name: "webhooks:delete",
    resource: "webhooks",
    action: "delete",
    description: "Delete webhooks",
    category: "integrations",
    is_system_permission: true,
  },

  // Integrations
  {
    name: "integrations:read",
    resource: "integrations",
    action: "read",
    description: "View integrations",
    category: "integrations",
    is_system_permission: true,
  },
  {
    name: "integrations:write",
    resource: "integrations",
    action: "write",
    description: "Create and update integrations",
    category: "integrations",
    is_system_permission: true,
  },
  {
    name: "integrations:delete",
    resource: "integrations",
    action: "delete",
    description: "Delete integrations",
    category: "integrations",
    is_system_permission: true,
  },

  // System administration
  {
    name: "system:read",
    resource: "system",
    action: "read",
    description: "View system status",
    category: "system",
    is_system_permission: true,
  },
  {
    name: "system:write",
    resource: "system",
    action: "write",
    description: "System configuration",
    category: "system",
    is_system_permission: true,
  },
  {
    name: "system:backup",
    resource: "system",
    action: "backup",
    description: "System backup operations",
    category: "system",
    is_system_permission: true,
  },
];

permissions.forEach((permission) => {
  permission.created_at = new Date().toISOString();
  db.permissions.insertOne(permission);
});

print("Setting up roles...");

// Insert system roles
const roles = [
  {
    name: "user",
    display_name: "Regular User",
    description: "Standard user with basic permissions",
    type: "system",
    tenant_id: null,
    permissions: ["tenants:switch"],
    inherits_from: null,
    is_system_role: true,
    is_default: true,
  },
  {
    name: "admin",
    display_name: "Administrator",
    description: "Admin user with user management permissions",
    type: "system",
    tenant_id: null,
    permissions: [
      "users:read",
      "users:write",
      "users:lock",
      "tenants:read",
      "tenants:manage_users",
      "tenants:invite_users",
      "tenants:switch",
      "audit:read",
      "roles:read",
      "roles:assign",
      "webhooks:read",
      "webhooks:write",
      "integrations:read",
      "integrations:write",
    ],
    inherits_from: null,
    is_system_role: true,
    is_default: false,
  },
  {
    name: "superadmin",
    display_name: "Super Administrator",
    description: "Full system access with all permissions",
    type: "system",
    tenant_id: null,
    permissions: [
      "users:read",
      "users:write",
      "users:delete",
      "users:lock",
      "users:impersonate",
      "tenants:read",
      "tenants:write",
      "tenants:delete",
      "tenants:manage_users",
      "tenants:manage_settings",
      "tenants:billing",
      "tenants:invite_users",
      "tenants:switch",
      "roles:read",
      "roles:write",
      "roles:delete",
      "roles:assign",
      "audit:read",
      "audit:export",
      "webhooks:read",
      "webhooks:write",
      "webhooks:delete",
      "integrations:read",
      "integrations:write",
      "integrations:delete",
      "system:read",
      "system:write",
      "system:backup",
    ],
    inherits_from: null,
    is_system_role: true,
    is_default: false,
  },
  {
    name: "support",
    display_name: "Support Staff",
    description: "Support team with limited admin access",
    type: "system",
    tenant_id: null,
    permissions: [
      "users:read",
      "users:lock",
      "tenants:read",
      "audit:read",
      "tenants:switch",
    ],
    inherits_from: null,
    is_system_role: true,
    is_default: false,
  },
  {
    name: "billing_admin",
    display_name: "Billing Administrator",
    description: "Billing management permissions",
    type: "system",
    tenant_id: null,
    permissions: [
      "users:read",
      "tenants:read",
      "tenants:billing",
      "audit:read",
      "tenants:switch",
    ],
    inherits_from: null,
    is_system_role: true,
    is_default: false,
  },
];

roles.forEach((role) => {
  role.created_at = new Date().toISOString();
  role.updated_at = null;
  role.created_by = null;
  role.metadata = {};
  db.roles.insertOne(role);
});

print("Setting up system configuration for auto-promotion...");

// System configuration for auto-promotion

const systemConfigs = [
  // --- System ---
  {
    key: "auto_promote_first_user",
    value: true,
    description:
      "Automatically promote the first registered user to superadmin",
    category: "system",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },
  {
    key: "superadmin_email",
    value: "superadmin@fileq.ai",
    description: "Email address that will be auto-promoted to superadmin",
    category: "system",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },
  {
    key: "system_initialized",
    value: true,
    description: "Whether the system has been initialized",
    category: "system",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },

  // --- Tenants ---
  {
    key: "default_tenant_plan",
    value: "trial",
    description: "Default subscription plan for new tenants",
    category: "tenants",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },
  {
    key: "trial_duration_days",
    value: 7,
    description: "Trial period duration in days",
    category: "tenants",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },

  // --- Security ---
  {
    key: "password_min_length",
    value: 8,
    description: "Minimum password length for all users",
    category: "security",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },
  {
    key: "password_pattern",
    value: 8,
    description: "Allowed password pattern for all users",
    category: "security",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },
  {
    key: "mfa_required",
    value: "always",
    description: "Require multi-factor authentication",
    category: "security",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },

  // --- API ---
  {
    key: "api_rate_limit_per_minute",
    value: 100,
    description: "Max API requests per user per minute",
    category: "api",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },
  {
    key: "cors_allowed_origins",
    value: ["https://app.yourcompany.com"],
    description: "Allowed origins for frontend apps",
    category: "api",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },

  // --- Compliance ---
  {
    key: "audit_log_enabled",
    value: true,
    description: "Enable system-wide audit logging",
    category: "compliance",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },
  {
    key: "audit_log_retention_days",
    value: 365,
    description: "Retention period for audit logs (days)",
    category: "compliance",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },

  // --- Monitoring ---
  {
    key: "notify_on_failed_login",
    value: true,
    description: "Send alerts on repeated failed login attempts",
    category: "monitoring",
    is_sensitive: false,
    created_at: new Date().toISOString(),
    updated_at: null,
    updated_by: null,
  },
];

systemConfigs.forEach((config) => {
  db.system_config.insertOne(config);
});

print("Creating utility functions...");

// Note: MongoDB stored JavaScript functions (db.system.js.save) are deprecated
// These functions should be implemented in your application code instead
// The following are example implementations that would be used in your Node.js/backend code

/*
Example utility functions to implement in your application:

// User permission checking
function getUserEffectivePermissions(userId, tenantId) {
  // Implementation would query users, roles, and tenant_users collections
  // Return array of permission strings
}

function userHasPermission(userId, permission, tenantId) {
  // Check if user has specific permission
  // Return boolean
}

// Tenant management
function getUserTenants(userId) {
  // Get all tenants user belongs to
  // Return array of tenant objects
}

function getTenantUsers(tenantId, role = null) {
  // Get all users in a tenant, optionally filtered by role
  // Return array of user objects with tenant role info
}

function isTenantAdmin(userId, tenantId) {
  // Check if user is admin/owner of tenant
  // Return boolean
}

// Audit helpers
function logAuditEvent(eventType, userId, details, tenantId) {
  // Insert audit log entry
  // Return insertion result
}

function getRecentActivity(tenantId, hours = 24) {
  // Get recent audit logs
  // Return array of audit log entries
}

// System utilities
function cleanupExpiredTokens() {
  // Clean up expired sessions, invitations, reset tokens
  // Return cleanup statistics
}

function getSystemStats() {
  // Get system statistics (user counts, tenant counts, etc.)
  // Return statistics object
}

// Validation helpers
function validateTenantSubdomain(subdomain) {
  // Validate subdomain format and availability
  // Return {valid: boolean, reason?: string}
}

function validatePermissionFormat(permission) {
  // Validate permission string format
  // Return {valid: boolean, reason?: string}
}

*/

print("Note: Utility functions should be implemented in your application code");
print("MongoDB stored JavaScript functions are deprecated and not recommended");

print("Creating initial audit log...");

// Insert initial audit log
db.audit_logs.insertOne({
  timestamp: new Date().toISOString(),
  event_type: "system_initialized",
  tenant_id: null,
  user_id: null,
  target_user_id: null,
  admin_user_id: null,
  ip_address: "127.0.0.1",
  user_agent: "MongoDB Init Script",
  details: {
    collections_created: [
      "users",
      "tenants",
      "tenant_users",
      "tenant_invitations",
      "roles",
      "permissions",
      "audit_logs",
      "sessions",
      "webhooks",
      "integrations",
      "system_config",
    ],
    permissions_count: permissions.length,
    roles_count: roles.length,
    auto_promotion_enabled: true,
  },
  severity: "info",
  session_id: "init_" + new Date().getTime(),
  action: "system_init",
  resource: "system",
  before_state: null,
  after_state: {
    system_initialized: true,
    auto_promotion_ready: true,
  },
  correlation_id: "system_init_" + new Date().getTime(),
});

print("MongoDB initialization completed successfully!");
print("Collections created:");
print("  - users (multi-tenant user management)");
print("  - tenants (tenant configuration)");
print("  - tenant_users (user-tenant relationships)");
print("  - tenant_invitations (invitation management)");
print("  - roles (RBAC roles)");
print("  - permissions (RBAC permissions)");
print("  - audit_logs (comprehensive audit trail)");
print("  - sessions (session management)");
print("  - webhooks (webhook management)");
print("  - integrations (third-party integrations)");
print("  - system_config (system configuration)");

print("Permissions system configured with", permissions.length, "permissions");
print("Role system configured with", roles.length, "roles");
print("Auto-promotion configured for first user");
print("Complete RBAC (Role-Based Access Control) system ready");
print("Multi-tenant architecture with comprehensive features");

print("\nIMPORTANT NEXT STEPS:");
print("1. Register first superadmin through Kratos: POST /auth/register");
print("2. Use email: superadmin@yourcompany.com for auto-promotion");
print("3. Update superadmin email in system_config for production");
print("4. Create your first tenant through the admin interface");
print("5. Configure Lago billing integration");
print("6. Set up proper encryption for sensitive fields");

print("\nDatabase Statistics:");
print("Roles:", db.roles.countDocuments());
print("Permissions:", db.permissions.countDocuments());
print("System Config:", db.system_config.countDocuments());
print("Audit Logs:", db.audit_logs.countDocuments());

print("\nComplete multi-tenant authentication system ready!");
print("Lago will handle all usage tracking and billing");
print("Auto-promotion will be disabled after first superadmin is created");
