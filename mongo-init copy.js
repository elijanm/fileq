db = db.getSiblingDB("auth_db");

// Create collections with validation
db.createCollection("users", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["email", "kratos_id", "created_at"],
      properties: {
        email: {
          bsonType: "string",
          pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
        },
        kratos_id: { bsonType: "string" },
        lago_customer_id: { bsonType: "string" },
        external_id: { bsonType: "string" },
        name: { bsonType: "string" },
        created_at: { bsonType: "string" },
        last_login: { bsonType: ["string", "null"] },
        last_login_ip: { bsonType: ["string", "null"] },
        failed_login_attempts: { bsonType: "int", minimum: 0 },
        account_locked: { bsonType: "bool" },
        locked_at: { bsonType: ["string", "null"] },
        terms_accepted: { bsonType: "bool" },
        marketing_consent: { bsonType: "bool" },
        registration_ip: { bsonType: "string" },
      },
    },
  },
});

db.createCollection("audit_logs", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["timestamp", "event_type", "severity"],
      properties: {
        timestamp: { bsonType: "string" },
        event_type: { bsonType: "string" },
        user_id: { bsonType: ["string", "null"] },
        ip_address: { bsonType: ["string", "null"] },
        user_agent: { bsonType: ["string", "null"] },
        details: { bsonType: "object" },
        severity: {
          bsonType: "string",
          enum: ["info", "warning", "error", "critical"],
        },
        session_id: { bsonType: "string" },
      },
    },
  },
});

// Enhanced mongo-init.js with multi-tenancy support

print("🚀 Initializing MongoDB for Multi-tenant Authentication Service...");

db = db.getSiblingDB("auth_db");

// Create tenants collection
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
                primary_color: { bsonType: ["string", "null"] },
                secondary_color: { bsonType: ["string", "null"] },
                custom_css: { bsonType: ["string", "null"] },
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
              },
            },
            security: {
              bsonType: "object",
              properties: {
                password_policy: { bsonType: "object" },
                session_timeout: { bsonType: ["int", "null"] },
                ip_whitelist: { bsonType: ["array", "null"] },
                allowed_domains: { bsonType: ["array", "null"] },
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
          },
        },
        created_at: { bsonType: "string" },
        updated_at: { bsonType: ["string", "null"] },
        created_by: { bsonType: ["string", "null"] },
        trial_ends_at: { bsonType: ["string", "null"] },
        last_activity: { bsonType: ["string", "null"] },
        metadata: { bsonType: ["object", "null"] },
      },
    },
  },
});

// Create tenant_users junction table for user-tenant relationships
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
          enum: ["owner", "admin", "user", "guest", "billing_admin"],
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
        created_at: { bsonType: "string" },
        updated_at: { bsonType: ["string", "null"] },
      },
    },
  },
});

// Update users collection to add tenant context
db.runCommand({
  collMod: "users",
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["email", "kratos_id", "created_at"],
      properties: {
        email: {
          bsonType: "string",
          pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
        },
        kratos_id: { bsonType: "string" },
        lago_customer_id: { bsonType: ["string", "null"] },
        external_id: { bsonType: ["string", "null"] },
        name: { bsonType: "string" },
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
        permissions: {
          bsonType: "array",
          items: { bsonType: "string" },
          description: "Global permissions",
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
        preferences: { bsonType: "object" },
      },
    },
  },
});

// Create tenant_invitations collection for managing invites
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
          enum: ["admin", "user", "guest", "billing_admin"],
        },
        permissions: {
          bsonType: "array",
          items: { bsonType: "string" },
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
          enum: ["pending", "accepted", "rejected", "expired"],
          description: "Invitation status",
        },
        created_at: { bsonType: "string" },
        expires_at: { bsonType: "string" },
        accepted_at: { bsonType: ["string", "null"] },
        rejected_at: { bsonType: ["string", "null"] },
      },
    },
  },
});

// Update audit_logs to include tenant context
db.runCommand({
  collMod: "audit_logs",
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
      },
    },
  },
});

print("📊 Creating indexes for multi-tenant performance...");

// Tenant indexes
db.tenants.createIndex({ subdomain: 1 }, { unique: true });
db.tenants.createIndex({ domain: 1 }, { unique: true, sparse: true });
db.tenants.createIndex({ status: 1 });
db.tenants.createIndex({ subscription_plan: 1 });
db.tenants.createIndex({ created_at: 1 });
db.tenants.createIndex({ trial_ends_at: 1 }, { sparse: true });

// Tenant-user relationship indexes
db.tenant_users.createIndex({ tenant_id: 1, user_id: 1 }, { unique: true });
db.tenant_users.createIndex({ tenant_id: 1, role: 1 });
db.tenant_users.createIndex({ user_id: 1 });
db.tenant_users.createIndex({ status: 1 });
db.tenant_users.createIndex({ tenant_id: 1, status: 1 });

// Tenant invitations indexes
db.tenant_invitations.createIndex({ tenant_id: 1 });
db.tenant_invitations.createIndex({ email: 1 });
db.tenant_invitations.createIndex({ token: 1 }, { unique: true });
db.tenant_invitations.createIndex({ status: 1 });
db.tenant_invitations.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 });

// Updated user indexes
db.users.createIndex({ primary_tenant_id: 1 });
db.users.createIndex({ global_role: 1 });
db.users.createIndex({ is_system_user: 1 });

// Updated audit log indexes
db.audit_logs.createIndex({ tenant_id: 1, timestamp: -1 });
db.audit_logs.createIndex({ tenant_id: 1, user_id: 1, timestamp: -1 });

print("🏢 Creating sample tenant and system configuration...");

// Create system tenant for global operations
const systemTenant = {
  name: "System Administration",
  subdomain: "system",
  domain: null,
  status: "active",
  subscription_plan: "enterprise",
  settings: {
    branding: {
      logo_url: null,
      primary_color: "#1f2937",
      secondary_color: "#374151",
    },
    features: {
      sso_enabled: true,
      mfa_required: true,
      api_access: true,
      audit_logs: true,
      custom_roles: true,
      integrations: [],
    },
    limits: {
      max_users: null,
      max_admins: null,
      storage_gb: null,
      api_calls_per_month: null,
    },
    security: {
      password_policy: {
        min_length: 12,
        require_uppercase: true,
        require_lowercase: true,
        require_numbers: true,
        require_special: true,
      },
      session_timeout: 86400,
      ip_whitelist: null,
      allowed_domains: null,
    },
  },
  billing_info: {
    lago_customer_id: null,
    stripe_customer_id: null,
    billing_email: null,
    billing_address: null,
  },
  created_at: new Date().toISOString(),
  updated_at: null,
  created_by: null,
  trial_ends_at: null,
  last_activity: new Date().toISOString(),
  metadata: {
    is_system_tenant: true,
    description: "System administration tenant",
  },
};

const systemTenantResult = db.tenants.insertOne(systemTenant);
const systemTenantId = systemTenantResult.insertedId;

print("System tenant ID:", systemTenantId);

// Create default tenant for general use
const defaultTenant = {
  name: "Default Organization",
  subdomain: "default",
  domain: null,
  status: "active",
  subscription_plan: "trial",
  settings: {
    branding: {
      logo_url: null,
      primary_color: "#3b82f6",
      secondary_color: "#1e40af",
    },
    features: {
      sso_enabled: false,
      mfa_required: false,
      api_access: true,
      audit_logs: true,
      custom_roles: false,
      integrations: [],
    },
    limits: {
      max_users: 100,
      max_admins: 5,
      storage_gb: 10,
      api_calls_per_month: 10000,
    },
    security: {
      password_policy: {
        min_length: 8,
        require_uppercase: true,
        require_lowercase: true,
        require_numbers: true,
        require_special: false,
      },
      session_timeout: 28800,
      ip_whitelist: null,
      allowed_domains: null,
    },
  },
  billing_info: {
    lago_customer_id: null,
    stripe_customer_id: null,
    billing_email: null,
    billing_address: null,
  },
  created_at: new Date().toISOString(),
  updated_at: null,
  created_by: null,
  trial_ends_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(), // 30 days from now
  last_activity: new Date().toISOString(),
  metadata: {
    is_default_tenant: true,
    description: "Default tenant for new users",
  },
};

const defaultTenantResult = db.tenants.insertOne(defaultTenant);
const defaultTenantId = defaultTenantResult.insertedId;

print("Default tenant ID:", defaultTenantId);

// Update system configuration to include tenant context
const multiTenantConfigs = [
  {
    key: "default_tenant_id",
    value: defaultTenantId.toString(),
    description: "Default tenant for new user registrations",
    created_at: new Date().toISOString(),
    updated_at: null,
  },
  {
    key: "system_tenant_id",
    value: systemTenantId.toString(),
    description: "System administration tenant",
    created_at: new Date().toISOString(),
    updated_at: null,
  },
  {
    key: "multi_tenant_mode",
    value: true,
    description: "Enable multi-tenant functionality",
    created_at: new Date().toISOString(),
    updated_at: null,
  },
  {
    key: "allow_tenant_creation",
    value: true,
    description: "Allow users to create new tenants",
    created_at: new Date().toISOString(),
    updated_at: null,
  },
];

multiTenantConfigs.forEach((config) => {
  db.system_config.insertOne(config);
});

print("🔐 Updated permissions for multi-tenancy...");

// Add multi-tenant permissions
const tenantPermissions = [
  {
    name: "tenants:read",
    resource: "tenants",
    action: "read",
    description: "View tenant information",
  },
  {
    name: "tenants:write",
    resource: "tenants",
    action: "write",
    description: "Create and update tenants",
  },
  {
    name: "tenants:delete",
    resource: "tenants",
    action: "delete",
    description: "Delete tenants",
  },
  {
    name: "tenants:manage_users",
    resource: "tenants",
    action: "manage_users",
    description: "Manage tenant users",
  },
  {
    name: "tenants:manage_settings",
    resource: "tenants",
    action: "manage_settings",
    description: "Manage tenant settings",
  },
  {
    name: "tenants:billing",
    resource: "tenants",
    action: "billing",
    description: "Manage tenant billing",
  },
  {
    name: "tenants:invite_users",
    resource: "tenants",
    action: "invite_users",
    description: "Invite users to tenant",
  },
  {
    name: "tenants:switch",
    resource: "tenants",
    action: "switch",
    description: "Switch between tenants",
  },
];

tenantPermissions.forEach((permission) => {
  permission.created_at = new Date().toISOString();
  db.permissions.insertOne(permission);
});

// Update roles with tenant permissions
db.roles.updateOne(
  { name: "superadmin" },
  {
    $addToSet: {
      permissions: {
        $each: [
          "tenants:read",
          "tenants:write",
          "tenants:delete",
          "tenants:manage_users",
          "tenants:manage_settings",
          "tenants:billing",
          "tenants:invite_users",
          "tenants:switch",
        ],
      },
    },
  }
);

db.roles.updateOne(
  { name: "admin" },
  {
    $addToSet: {
      permissions: {
        $each: [
          "tenants:read",
          "tenants:manage_users",
          "tenants:invite_users",
          "tenants:switch",
        ],
      },
    },
  }
);

// Add tenant-specific roles
const tenantRoles = [
  {
    name: "tenant_owner",
    display_name: "Tenant Owner",
    description: "Owner of a tenant with full permissions",
    permissions: [
      "tenants:read",
      "tenants:write",
      "tenants:manage_users",
      "tenants:manage_settings",
      "tenants:billing",
      "tenants:invite_users",
      "users:read",
      "users:write",
      "users:lock",
      "audit:read",
    ],
    is_system_role: true,
    created_at: new Date().toISOString(),
    updated_at: null,
    created_by: null,
  },
  {
    name: "tenant_admin",
    display_name: "Tenant Administrator",
    description: "Administrator within a tenant",
    permissions: [
      "tenants:read",
      "tenants:manage_users",
      "tenants:invite_users",
      "users:read",
      "users:write",
      "audit:read",
    ],
    is_system_role: true,
    created_at: new Date().toISOString(),
    updated_at: null,
    created_by: null,
  },
];

tenantRoles.forEach((role) => {
  db.roles.insertOne(role);
});

print("✅ Multi-tenant MongoDB initialization completed!");
print("🏢 Collections: tenants, tenant_users, tenant_invitations");
print("👥 System tenant ID:", systemTenantId);
print("🏠 Default tenant ID:", defaultTenantId);
print("🔐 Added tenant-specific permissions and roles");
print("📊 Multi-tenant indexes created for performance");

print("\n🎉 Multi-tenant authentication system ready!");

// Create indexes for performance
db.users.createIndex({ email: 1 }, { unique: true });
db.users.createIndex({ kratos_id: 1 }, { unique: true });
db.users.createIndex({ lago_customer_id: 1 });
db.users.createIndex({ created_at: 1 });
db.users.createIndex({ account_locked: 1 });

db.audit_logs.createIndex({ timestamp: 1 });
db.audit_logs.createIndex({ event_type: 1 });
db.audit_logs.createIndex({ user_id: 1 });
db.audit_logs.createIndex({ severity: 1 });
db.audit_logs.createIndex({ ip_address: 1 });

// TTL index for audit log cleanup (90 days)
db.audit_logs.createIndex({ timestamp: 1 }, { expireAfterSeconds: 7776000 });
