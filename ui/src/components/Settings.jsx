import React, { useState } from "react";
import {
  Users,
  HardDrive,
  Palette,
  Lock,
  CreditCard,
  Upload,
  Edit,
  Check,
  AlertCircle,
  Trash2,
  Archive,
  Crown,
  RefreshCw,
} from "lucide-react";
import PaymentIntegrationSettings from "@/components/PaymentIntegrationSettings";
export default function Settings({ user, setUser }) {
  const [activeTab, setActiveTab] = useState("profile");

  // Button component
  const Button = ({
    children,
    onClick,
    variant = "default",
    size = "default",
    className,
    disabled,
    ...props
  }) => {
    const baseClasses =
      "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
    const variants = {
      default: "bg-blue-600 text-white hover:bg-blue-700",
      outline: "border border-slate-200 bg-white hover:bg-slate-100",
      ghost: "hover:bg-slate-100",
      destructive: "bg-red-600 text-white hover:bg-red-700",
    };
    const sizes = {
      default: "h-10 py-2 px-4",
      sm: "h-9 px-3 text-sm",
      lg: "h-11 px-8",
    };

    return (
      <button
        className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${
          className || ""
        }`}
        onClick={onClick}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    );
  };

  // Card component
  const Card = ({ children, className }) => (
    <div
      className={`bg-white rounded-lg shadow border border-slate-200 ${
        className || ""
      }`}
    >
      {children}
    </div>
  );

  const CardContent = ({ children, className }) => (
    <div className={`p-6 ${className || ""}`}>{children}</div>
  );

  const tabs = [
    { id: "profile", label: "Profile", icon: Users },
    { id: "storage", label: "Storage", icon: HardDrive },
    { id: "appearance", label: "Appearance", icon: Palette },
    { id: "payments", label: "Payments", icon: CreditCard },
    { id: "security", label: "Security", icon: Lock },
    { id: "billing", label: "Billing", icon: CreditCard },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <main className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-slate-900">Settings</h1>
        </div>

        <div className="flex gap-8">
          {/* Sidebar */}
          <div className="w-64 space-y-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition-all ${
                    activeTab === tab.id
                      ? "bg-blue-100 text-blue-600 font-medium"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Content */}
          <div className="flex-1">
            <Card className="bg-white shadow-lg border-0">
              <CardContent className="p-8">
                {activeTab === "profile" && (
                  <ProfileSettings user={user} setUser={setUser} />
                )}
                {activeTab === "storage" && <StorageSettings />}
                {activeTab === "appearance" && <AppearanceSettings />}
                {activeTab === "security" && <SecuritySettings user={user} />}
                {activeTab === "billing" && <BillingSettings user={user} />}
                {activeTab === "payments" && (
                  <PaymentIntegrationSettings user={user} userLocation="KE" />
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}

// Profile Settings Tab
function ProfileSettings({ user, setUser }) {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    name: user.name,
    email: user.email,
  });

  // Button component
  const Button = ({
    children,
    onClick,
    variant = "default",
    size = "default",
    className,
    disabled,
    ...props
  }) => {
    const baseClasses =
      "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
    const variants = {
      default: "bg-blue-600 text-white hover:bg-blue-700",
      outline: "border border-slate-200 bg-white hover:bg-slate-100",
      ghost: "hover:bg-slate-100",
    };
    const sizes = {
      default: "h-10 py-2 px-4",
      sm: "h-9 px-3 text-sm",
    };

    return (
      <button
        className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${
          className || ""
        }`}
        onClick={onClick}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    );
  };

  const handleSave = () => {
    setUser((prev) => ({ ...prev, ...formData }));
    setIsEditing(false);
  };

  const handleVerifyEmail = () => {
    // Simulate email verification
    setTimeout(() => {
      setUser((prev) => ({ ...prev, isEmailVerified: true }));
      alert("Email verified successfully!");
    }, 1000);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">
          Profile Settings
        </h2>
        <p className="text-slate-600">
          Manage your account information and preferences.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {/* Profile Picture */}
        <div className="flex items-center space-x-6">
          <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-full flex items-center justify-center shadow-lg">
            <span className="text-white font-bold text-2xl">
              {user.name?.charAt(0) || "U"}
            </span>
          </div>
          <div>
            <Button variant="outline">
              <Upload className="w-4 h-4 mr-2" />
              Change Avatar
            </Button>
            <p className="text-sm text-slate-500 mt-2">
              JPG, PNG or GIF. Max size 2MB.
            </p>
          </div>
        </div>

        {/* Name */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Full Name
          </label>
          <div className="flex items-center space-x-4">
            <input
              type="text"
              value={formData.name}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, name: e.target.value }))
              }
              disabled={!isEditing}
              className="flex-1 border border-slate-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-slate-50"
            />
            {!isEditing && (
              <Button onClick={() => setIsEditing(true)} variant="outline">
                <Edit className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>

        {/* Email */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Email Address
          </label>
          <div className="flex items-center space-x-4">
            <input
              type="email"
              value={formData.email}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, email: e.target.value }))
              }
              disabled={!isEditing}
              className="flex-1 border border-slate-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-slate-50"
            />
            <div className="flex items-center space-x-2">
              {user.isEmailVerified ? (
                <div className="flex items-center space-x-2 text-green-600">
                  <Check className="w-4 h-4" />
                  <span className="text-sm">Verified</span>
                </div>
              ) : (
                <Button onClick={handleVerifyEmail} variant="outline" size="sm">
                  Verify
                </Button>
              )}
            </div>
          </div>
          {!user.isEmailVerified && (
            <p className="text-sm text-amber-600 mt-2 flex items-center">
              <AlertCircle className="w-4 h-4 mr-2" />
              Please verify your email to access all features
            </p>
          )}
        </div>

        {/* Save/Cancel Buttons */}
        {isEditing && (
          <div className="flex items-center space-x-4 pt-4 border-t border-slate-200">
            <Button onClick={handleSave}>Save Changes</Button>
            <Button onClick={() => setIsEditing(false)} variant="outline">
              Cancel
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

// Storage Settings Tab
function StorageSettings() {
  const storageData = {
    used: 4.2,
    total: 5.0,
    breakdown: [
      { type: "Documents", size: 1.8, color: "#3b82f6" },
      { type: "Images", size: 1.2, color: "#10b981" },
      { type: "Videos", size: 0.8, color: "#f59e0b" },
      { type: "Archives", size: 0.4, color: "#8b5cf6" },
    ],
  };

  // Button component
  const Button = ({
    children,
    onClick,
    variant = "default",
    size = "default",
    className,
    disabled,
    ...props
  }) => {
    const baseClasses =
      "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
    const variants = {
      default: "bg-blue-600 text-white hover:bg-blue-700",
      outline: "border border-slate-200 bg-white hover:bg-slate-100",
      ghost: "hover:bg-slate-100",
    };
    const sizes = {
      default: "h-10 py-2 px-4",
      sm: "h-9 px-3 text-sm",
    };

    return (
      <button
        className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${
          className || ""
        }`}
        onClick={onClick}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">
          Storage Management
        </h2>
        <p className="text-slate-600">
          Monitor your storage usage and manage your files.
        </p>
      </div>

      {/* Storage Overview */}
      <div className="bg-slate-50 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-900">
            Storage Usage
          </h3>
          <div className="text-sm text-slate-600">
            {storageData.used}GB of {storageData.total}GB used
          </div>
        </div>

        <div className="w-full bg-slate-200 rounded-full h-4 mb-4">
          <div
            className="bg-gradient-to-r from-blue-500 to-cyan-500 h-4 rounded-full transition-all duration-500"
            style={{
              width: `${(storageData.used / storageData.total) * 100}%`,
            }}
          ></div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {storageData.breakdown.map((item, index) => (
            <div key={item.type} className="text-center">
              <div
                className="w-4 h-4 rounded mx-auto mb-2"
                style={{ backgroundColor: item.color }}
              ></div>
              <div className="text-sm font-medium text-slate-900">
                {item.type}
              </div>
              <div className="text-xs text-slate-600">{item.size}GB</div>
            </div>
          ))}
        </div>
      </div>

      {/* Storage Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Button variant="outline" className="p-6 h-auto flex-col space-y-2">
          <Trash2 className="w-8 h-8 text-red-500" />
          <span className="font-medium">Clean Up Files</span>
          <span className="text-sm text-slate-500 text-center">
            Remove duplicates and old files
          </span>
        </Button>

        <Button variant="outline" className="p-6 h-auto flex-col space-y-2">
          <Archive className="w-8 h-8 text-blue-500" />
          <span className="font-medium">Archive Old Files</span>
          <span className="text-sm text-slate-500 text-center">
            Move old files to archive
          </span>
        </Button>

        <Button variant="outline" className="p-6 h-auto flex-col space-y-2">
          <Crown className="w-8 h-8 text-yellow-500" />
          <span className="font-medium">Upgrade Storage</span>
          <span className="text-sm text-slate-500 text-center">
            Get more space
          </span>
        </Button>
      </div>
    </div>
  );
}

// Appearance Settings Tab
function AppearanceSettings() {
  const [theme, setTheme] = useState("light");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Appearance</h2>
        <p className="text-slate-600">
          Customize how FileQ looks and feels for you.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-3">
            Theme
          </label>
          <div className="grid grid-cols-3 gap-4">
            {[
              { id: "light", name: "Light", preview: "bg-white" },
              { id: "dark", name: "Dark", preview: "bg-slate-900" },
              {
                id: "auto",
                name: "Auto",
                preview: "bg-gradient-to-r from-white to-slate-900",
              },
            ].map((themeOption) => (
              <button
                key={themeOption.id}
                onClick={() => setTheme(themeOption.id)}
                className={`p-4 rounded-lg border-2 transition-all ${
                  theme === themeOption.id
                    ? "border-blue-500"
                    : "border-slate-200"
                }`}
              >
                <div
                  className={`w-full h-12 rounded mb-3 ${themeOption.preview}`}
                ></div>
                <div className="text-sm font-medium">{themeOption.name}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// Security Settings Tab
function SecuritySettings({ user }) {
  // Button component
  const Button = ({
    children,
    onClick,
    variant = "default",
    size = "default",
    className,
    disabled,
    ...props
  }) => {
    const baseClasses =
      "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
    const variants = {
      default: "bg-blue-600 text-white hover:bg-blue-700",
      outline: "border border-slate-200 bg-white hover:bg-slate-100",
      ghost: "hover:bg-slate-100",
    };
    const sizes = {
      default: "h-10 py-2 px-4",
      sm: "h-9 px-3 text-sm",
    };

    return (
      <button
        className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${
          className || ""
        }`}
        onClick={onClick}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Security</h2>
        <p className="text-slate-600">
          Manage your account security and privacy settings.
        </p>
      </div>

      <div className="space-y-6">
        {/* Password */}
        <div className="border-b border-slate-200 pb-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">
            Password
          </h3>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-600">
                Change your password regularly to keep your account secure.
              </p>
            </div>
            <Button variant="outline">Change Password</Button>
          </div>
        </div>

        {/* Two-Factor Authentication */}
        <div className="border-b border-slate-200 pb-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">
            Two-Factor Authentication
          </h3>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-600">
                Add an extra layer of security to your account.
              </p>
              <p className="text-sm text-slate-500 mt-1">Status: Not enabled</p>
            </div>
            <Button variant="outline">Enable 2FA</Button>
          </div>
        </div>

        {/* Login Sessions */}
        <div>
          <h3 className="text-lg font-semibold text-slate-900 mb-4">
            Active Sessions
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
              <div>
                <p className="font-medium text-slate-900">Current Session</p>
                <p className="text-sm text-slate-600">
                  Chrome on macOS • Bellevue, WA
                </p>
                <p className="text-sm text-slate-500">Last active: Now</p>
              </div>
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Billing Settings Tab
function BillingSettings({ user }) {
  // Button component
  const Button = ({
    children,
    onClick,
    variant = "default",
    size = "default",
    className,
    disabled,
    ...props
  }) => {
    const baseClasses =
      "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
    const variants = {
      default: "bg-blue-600 text-white hover:bg-blue-700",
      outline: "border border-slate-200 bg-white hover:bg-slate-100",
      ghost: "hover:bg-slate-100",
    };
    const sizes = {
      default: "h-10 py-2 px-4",
      sm: "h-9 px-3 text-sm",
    };

    return (
      <button
        className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${
          className || ""
        }`}
        onClick={onClick}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">
          Billing & Subscription
        </h2>
        <p className="text-slate-600">
          Manage your subscription and billing information.
        </p>
      </div>

      {/* Current Plan */}
      <div className="bg-slate-50 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-900">Current Plan</h3>
          <div
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              user.plan === "free"
                ? "bg-gray-100 text-gray-800"
                : "bg-blue-100 text-blue-800"
            }`}
          >
            {user?.plan?.charAt(0)?.toUpperCase() + user.plan?.slice(1)} Plan
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-slate-900">5GB</div>
            <div className="text-sm text-slate-600">Storage</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-slate-900">100</div>
            <div className="text-sm text-slate-600">Files per month</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-slate-900">∞</div>
            <div className="text-sm text-slate-600">Downloads</div>
          </div>
        </div>

        {user.plan === "free" && (
          <Button className="w-full bg-gradient-to-r from-blue-500 to-cyan-500 text-white">
            <Crown className="w-4 h-4 mr-2" />
            Upgrade to Pro
          </Button>
        )}
      </div>
    </div>
  );
}
