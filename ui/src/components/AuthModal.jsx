// components/AuthModal.jsx
import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  X,
  Mail,
  Lock,
  User,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { authAPI, utils } from "@/lib/api";

export default function AuthModal({
  isOpen,
  onClose,
  mode,
  onSwitchMode,
  onSuccess,
}) {
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    name: "",
    confirmPassword: "",
    terms_accepted: false,
    marketing_consent: false,
    remember_me: false,
  });

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [validationErrors, setValidationErrors] = useState({});

  // Reset form when modal opens/closes or mode changes
  useEffect(() => {
    if (isOpen) {
      resetForm();
    }
  }, [isOpen, mode]);

  const resetForm = () => {
    setFormData({
      email: "",
      password: "",
      name: "",
      confirmPassword: "",
      terms_accepted: false,
      marketing_consent: false,
      remember_me: false,
    });
    setError("");
    setSuccess("");
    setValidationErrors({});
    setShowPassword(false);
    setShowConfirmPassword(false);
  };

  const validateForm = () => {
    const errors = {};

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!formData.email) {
      errors.email = "Email is required";
    } else if (!emailRegex.test(formData.email)) {
      errors.email = "Please enter a valid email address";
    }

    // Password validation
    if (mode !== "forgot") {
      if (!formData.password) {
        errors.password = "Password is required";
      } else if (mode === "register" && formData.password.length < 8) {
        errors.password = "Password must be at least 8 characters long";
      }
    }

    // Registration specific validation
    if (mode === "register") {
      if (!formData.name.trim()) {
        errors.name = "Full name is required";
      }

      if (!formData.confirmPassword) {
        errors.confirmPassword = "Please confirm your password";
      } else if (formData.password !== formData.confirmPassword) {
        errors.confirmPassword = "Passwords do not match";
      }

      if (!formData.terms_accepted) {
        errors.terms_accepted = "You must accept the Terms of Service";
      }
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setLoading(true);
    setError("");
    setSuccess("");

    try {
      if (mode === "register") {
        const result = await authAPI.register({
          email: formData.email,
          password: formData.password,
          name: formData.name,
          terms_accepted: formData.terms_accepted,
          marketing_consent: formData.marketing_consent,
          preferred_language: "en",
        });

        utils.setAuthToken(result.access_token);
        setSuccess("Account created successfully! Welcome to FileQ.");

        setTimeout(() => {
          onSuccess &&
            onSuccess({
              name: formData.name,
              email: formData.email,
            });
          onClose();
        }, 1000);
      } else if (mode === "login") {
        const result = await authAPI.login({
          email: formData.email,
          password: formData.password,
          remember_me: formData.remember_me,
        });

        utils.setAuthToken(result.access_token);
        utils.setUser(result.user);
        setSuccess("Signed in successfully! Welcome back.");

        setTimeout(() => {
          onSuccess &&
            onSuccess({
              email: formData.email,
              name: result.user.name,
            });
          onClose();
        }, 1000);
      } else if (mode === "forgot") {
        await authAPI.forgotPassword(formData.email);
        setSuccess("Password reset link sent! Check your email inbox.");

        setTimeout(() => {
          onSwitchMode("login");
        }, 2000);
      }
    } catch (err) {
      setError(
        err.message || "An unexpected error occurred. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleModeSwitch = (newMode) => {
    resetForm();
    onSwitchMode(newMode);
  };

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));

    // Clear validation error when user starts typing
    if (validationErrors[field]) {
      setValidationErrors((prev) => ({ ...prev, [field]: "" }));
    }
  };

  if (!isOpen) return null;

  const getTitle = () => {
    switch (mode) {
      case "register":
        return "Create Your Account";
      case "login":
        return "Welcome Back";
      case "forgot":
        return "Reset Your Password";
      default:
        return "Authentication";
    }
  };

  const getSubtitle = () => {
    switch (mode) {
      case "register":
        return "Join thousands of users who trust FileQ";
      case "login":
        return "Sign in to access your files";
      case "forgot":
        return "Enter your email to receive a reset link";
      default:
        return "";
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center p-6 pb-4 border-b border-slate-100">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">{getTitle()}</h2>
            <p className="text-slate-600 text-sm mt-1">{getSubtitle()}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            disabled={loading}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Status Messages */}
          {error && (
            <div className="flex items-center p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
              <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
              {error}
            </div>
          )}

          {success && (
            <div className="flex items-center p-3 bg-green-50 border border-green-200 rounded-lg text-green-600 text-sm">
              <CheckCircle2 className="w-4 h-4 mr-2 flex-shrink-0" />
              {success}
            </div>
          )}

          {/* Name Field (Register only) */}
          {mode === "register" && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Full Name *
              </label>
              <div className="relative">
                <User className="absolute left-3 top-3 w-5 h-5 text-slate-400" />
                <input
                  type="text"
                  required
                  className={`w-full pl-10 pr-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors ${
                    validationErrors.name
                      ? "border-red-300"
                      : "border-slate-200"
                  }`}
                  placeholder="Enter your full name"
                  value={formData.name}
                  onChange={(e) => handleInputChange("name", e.target.value)}
                  disabled={loading}
                />
              </div>
              {validationErrors.name && (
                <p className="text-red-600 text-sm mt-1">
                  {validationErrors.name}
                </p>
              )}
            </div>
          )}

          {/* Email Field */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Email Address *
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-3 w-5 h-5 text-slate-400" />
              <input
                type="email"
                required
                className={`w-full pl-10 pr-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors ${
                  validationErrors.email ? "border-red-300" : "border-slate-200"
                }`}
                placeholder="Enter your email address"
                value={formData.email}
                onChange={(e) => handleInputChange("email", e.target.value)}
                disabled={loading}
              />
            </div>
            {validationErrors.email && (
              <p className="text-red-600 text-sm mt-1">
                {validationErrors.email}
              </p>
            )}
          </div>

          {/* Password Field */}
          {mode !== "forgot" && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Password *
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 w-5 h-5 text-slate-400" />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  className={`w-full pl-10 pr-12 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors ${
                    validationErrors.password
                      ? "border-red-300"
                      : "border-slate-200"
                  }`}
                  placeholder="Enter your password"
                  value={formData.password}
                  onChange={(e) =>
                    handleInputChange("password", e.target.value)
                  }
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-3 text-slate-400 hover:text-slate-600 transition-colors"
                  disabled={loading}
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>
              {validationErrors.password && (
                <p className="text-red-600 text-sm mt-1">
                  {validationErrors.password}
                </p>
              )}
              {mode === "register" && !validationErrors.password && (
                <p className="text-slate-500 text-xs mt-1">
                  Password must be at least 8 characters long
                </p>
              )}
            </div>
          )}

          {/* Confirm Password (Register only) */}
          {mode === "register" && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Confirm Password *
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 w-5 h-5 text-slate-400" />
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  required
                  className={`w-full pl-10 pr-12 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors ${
                    validationErrors.confirmPassword
                      ? "border-red-300"
                      : "border-slate-200"
                  }`}
                  placeholder="Confirm your password"
                  value={formData.confirmPassword}
                  onChange={(e) =>
                    handleInputChange("confirmPassword", e.target.value)
                  }
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-3 text-slate-400 hover:text-slate-600 transition-colors"
                  disabled={loading}
                >
                  {showConfirmPassword ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>
              {validationErrors.confirmPassword && (
                <p className="text-red-600 text-sm mt-1">
                  {validationErrors.confirmPassword}
                </p>
              )}
            </div>
          )}

          {/* Remember Me (Login only) */}
          {mode === "login" && (
            <div className="flex items-center justify-between">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  checked={formData.remember_me}
                  onChange={(e) =>
                    handleInputChange("remember_me", e.target.checked)
                  }
                  disabled={loading}
                />
                <span className="ml-2 text-sm text-slate-600">Remember me</span>
              </label>
              <button
                type="button"
                onClick={() => handleModeSwitch("forgot")}
                className="text-sm text-blue-600 hover:text-blue-700 transition-colors"
                disabled={loading}
              >
                Forgot password?
              </button>
            </div>
          )}

          {/* Terms and Marketing (Register only) */}
          {mode === "register" && (
            <div className="space-y-3">
              <label className="flex items-start">
                <input
                  type="checkbox"
                  required
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 mt-1"
                  checked={formData.terms_accepted}
                  onChange={(e) =>
                    handleInputChange("terms_accepted", e.target.checked)
                  }
                  disabled={loading}
                />
                <span className="ml-2 text-sm text-slate-600">
                  I agree to the{" "}
                  <a
                    href="#"
                    className="text-blue-600 hover:text-blue-700 transition-colors"
                  >
                    Terms of Service
                  </a>{" "}
                  and{" "}
                  <a
                    href="#"
                    className="text-blue-600 hover:text-blue-700 transition-colors"
                  >
                    Privacy Policy
                  </a>{" "}
                  *
                </span>
              </label>
              {validationErrors.terms_accepted && (
                <p className="text-red-600 text-sm">
                  {validationErrors.terms_accepted}
                </p>
              )}

              <label className="flex items-start">
                <input
                  type="checkbox"
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 mt-1"
                  checked={formData.marketing_consent}
                  onChange={(e) =>
                    handleInputChange("marketing_consent", e.target.checked)
                  }
                  disabled={loading}
                />
                <span className="ml-2 text-sm text-slate-600">
                  Send me product updates and marketing emails (optional)
                </span>
              </label>
            </div>
          )}

          {/* Submit Button */}
          <Button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-700 transition-colors"
            size="lg"
            disabled={loading}
          >
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {loading
              ? "Processing..."
              : mode === "register"
              ? "Create Account"
              : mode === "login"
              ? "Sign In"
              : "Send Reset Link"}
          </Button>
        </form>

        {/* Footer */}
        <div className="px-6 pb-6 text-center border-t border-slate-100 pt-6">
          <p className="text-sm text-slate-600">
            {mode === "register"
              ? "Already have an account?"
              : mode === "login"
              ? "Don't have an account?"
              : "Remember your password?"}
            <button
              onClick={() =>
                handleModeSwitch(
                  mode === "register"
                    ? "login"
                    : mode === "login"
                    ? "register"
                    : "login"
                )
              }
              className="ml-1 text-blue-600 hover:text-blue-700 font-medium transition-colors"
              disabled={loading}
            >
              {mode === "register"
                ? "Sign in"
                : mode === "login"
                ? "Sign up"
                : "Sign in"}
            </button>
          </p>

          {/* Demo Account Info (Login only) */}
          {mode === "login" && (
            <></>
            // <div className="mt-4 p-3 bg-slate-50 rounded-lg">
            //   <p className="text-xs text-slate-600 mb-2">
            //     Demo accounts for testing:
            //   </p>
            //   <div className="text-xs text-slate-500 space-y-1">
            //     <p>
            //       <strong>User:</strong> user@demo.com / demo123
            //     </p>
            //     <p>
            //       <strong>Admin:</strong> admin@demo.com / admin123
            //     </p>
            //   </div>
            // </div>
          )}
        </div>
      </div>
    </div>
  );
}
