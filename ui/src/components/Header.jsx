import React, { useState, useEffect } from "react";
import {
  Home,
  Files,
  Users,
  Settings,
  Bell,
  Search,
  Crown,
  LogOut,
  X,
  Check,
  Mail,
  Send,
  RefreshCw,
  AlertCircle,
} from "lucide-react";

export default function Header({
  user,
  currentView,
  setCurrentView,
  notifications,
  setNotifications,
  showNotifications,
  setShowNotifications,
  onLogout,
}) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  const unreadCount = notifications.filter((n) => n.unread).length;

  const navigationItems = [
    // { id: "dashboard", label: "Dashboard", icon: Home },
    { id: "files", label: "Files", icon: Files },
    { id: "teams", label: "Teams", icon: Users },
    { id: "settings", label: "Settings", icon: Settings },
  ];

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
      outline:
        "border border-slate-200 bg-white hover:bg-slate-100 hover:text-slate-900",
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
    <>
      <header className="bg-white/95 backdrop-blur-md border-b border-slate-200/60 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex justify-between items-center h-18 py-4">
            {/* Left side - Logo and Navigation */}
            <div className="flex items-center space-x-8">
              <div className="flex items-center space-x-3">
                <div
                  className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent cursor-pointer"
                  onClick={() => setCurrentView("dashboard")}
                >
                  FileQ
                </div>
                <div className="px-2 py-1 bg-blue-100 text-blue-600 text-xs rounded-full font-medium">
                  {currentView.charAt(0).toUpperCase() + currentView.slice(1)}
                </div>
              </div>

              {/* Navigation */}
              <nav className="hidden lg:flex items-center space-x-1">
                {navigationItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = currentView === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => setCurrentView(item.id)}
                      className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all duration-200 ${
                        isActive
                          ? "bg-blue-100 text-blue-600 font-medium"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span>{item.label}</span>
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* Right side */}
            <div className="flex items-center space-x-4">
              {/* Search */}
              <div className="relative hidden md:block">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search files..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-4 py-2 w-64 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all bg-white"
                />
              </div>

              {/* Upgrade Button */}
              {user.plan === "free" && (
                <Button
                  onClick={() => setCurrentView("upgrade")}
                  className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white hover:from-yellow-600 hover:to-orange-600"
                  size="sm"
                >
                  <Crown className="w-4 h-4 mr-2" />
                  Upgrade
                </Button>
              )}

              {/* Notifications */}
              <div className="relative">
                <Button
                  variant="outline"
                  size="sm"
                  className="relative"
                  onClick={() => setShowNotifications(!showNotifications)}
                >
                  <Bell className="w-4 h-4" />
                  {unreadCount > 0 && (
                    <div className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center font-medium">
                      {unreadCount}
                    </div>
                  )}
                </Button>

                {/* Notifications Dropdown */}
                {showNotifications && (
                  <NotificationsDropdown
                    notifications={notifications}
                    setNotifications={setNotifications}
                    onClose={() => setShowNotifications(false)}
                  />
                )}
              </div>

              {/* User menu */}
              <div className="flex items-center space-x-3 pl-4 border-l border-slate-200">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-full flex items-center justify-center shadow-lg">
                  <span className="text-white font-semibold text-sm">
                    {user?.name?.charAt(0) || "U"}
                  </span>
                </div>
                <div className="hidden md:block">
                  <div className="text-sm font-semibold text-slate-900">
                    {user?.name || "User"}
                  </div>
                  <div className="text-xs text-slate-500 capitalize">
                    {user?.plan} Plan
                    {user?.plan === "free" && (
                      <button
                        onClick={() => setCurrentView("upgrade")}
                        className="ml-2 text-blue-600 hover:text-blue-800"
                      >
                        Upgrade
                      </button>
                    )}
                  </div>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={onLogout}
                  className="text-slate-600 hover:text-red-600 border-slate-200"
                >
                  <LogOut className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Email Verification Banner */}
      {!user.isEmailVerified && <EmailVerificationBanner user={user} />}
    </>
  );
}

// Email Verification Banner
function EmailVerificationBanner({ user }) {
  const [isVisible, setIsVisible] = useState(true);
  const [isResending, setIsResending] = useState(false);

  const handleResendVerification = async () => {
    setIsResending(true);
    // Simulate API call
    setTimeout(() => {
      setIsResending(false);
      alert("Verification email sent!");
    }, 1000);
  };

  if (!isVisible) return null;

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
      outline: "border border-amber-300 text-amber-700 hover:bg-amber-100",
      ghost: "hover:bg-slate-100 text-amber-600 hover:text-amber-800",
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
    <div className="bg-gradient-to-r from-amber-50 to-yellow-50 border-b border-amber-200">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Mail className="w-5 h-5 text-amber-600" />
            <div>
              <span className="text-amber-800 font-medium">
                Please verify your email address to access all features.
              </span>
              <span className="text-amber-700 ml-2">
                Check your inbox at {user.email}
              </span>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <Button
              onClick={handleResendVerification}
              disabled={isResending}
              variant="outline"
              size="sm"
            >
              {isResending ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Resend
                </>
              )}
            </Button>
            <Button
              onClick={() => setIsVisible(false)}
              variant="ghost"
              size="sm"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Notifications Dropdown
function NotificationsDropdown({ notifications, setNotifications, onClose }) {
  const markAsRead = (id) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, unread: false } : n))
    );
  };

  const markAllAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, unread: false })));
  };

  const getNotificationIcon = (type) => {
    switch (type) {
      case "warning":
        return <AlertCircle className="w-5 h-5 text-amber-500" />;
      case "success":
        return <Check className="w-5 h-5 text-green-500" />;
      case "info":
        return <Bell className="w-5 h-5 text-blue-500" />;
      default:
        return <Bell className="w-5 h-5 text-slate-500" />;
    }
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
      outline:
        "border border-slate-200 bg-white hover:bg-slate-100 hover:text-slate-900",
      ghost: "hover:bg-slate-100",
    };
    const sizes = {
      default: "h-10 py-2 px-4",
      sm: "h-9 px-3 text-sm text-xs",
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
    <div className="absolute right-0 top-full mt-2 w-96 bg-white rounded-xl shadow-xl border border-slate-200 py-2 z-50">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-100">
        <h3 className="font-semibold text-slate-900">Notifications</h3>
        <div className="flex items-center space-x-2">
          <Button onClick={markAllAsRead} variant="ghost" size="sm">
            Mark all read
          </Button>
          <Button onClick={onClose} variant="ghost" size="sm">
            <X className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="max-h-96 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="px-4 py-8 text-center text-slate-500">
            <Bell className="w-8 h-8 mx-auto mb-2 text-slate-300" />
            <p>No notifications</p>
          </div>
        ) : (
          notifications.map((notification) => (
            <div
              key={notification.id}
              className={`px-4 py-3 hover:bg-slate-50 cursor-pointer transition-colors ${
                notification.unread ? "bg-blue-50/50" : ""
              }`}
              onClick={() => markAsRead(notification.id)}
            >
              <div className="flex items-start space-x-3">
                {getNotificationIcon(notification.type)}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <p className="text-sm font-medium text-slate-900 truncate">
                      {notification.title}
                    </p>
                    {notification.unread && (
                      <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                    )}
                  </div>
                  <p className="text-sm text-slate-600 mt-1">
                    {notification.message}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    {notification.time}
                  </p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
