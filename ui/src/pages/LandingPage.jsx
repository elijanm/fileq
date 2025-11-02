// FileQLanding.jsx - Main Landing Page with Dashboard Integration
import React, { useState, useRef, useCallback, useEffect } from "react";
import Navigation from "@/components/Navigation";
import HeroSection from "@/components/HeroSection";
import UploadSection from "@/components/UploadSection";
import FileDetailsSection from "@/components/FileDetailsSection";
import ToolsGrid from "@/components/ToolsGrid";
import FeatureHighlights from "@/components/FeatureHighlights";
import DeveloperSection from "@/components/DeveloperSection";
import PricingSection from "@/components/PricingSection";
import Footer from "@/components/FooterSection";
import Dashboard from "@/components/Dashboard";
import FileManager from "@/components/FileManager";
import Settings from "@/components/Settings";
import UpgradePlan from "@/components/UpgradePlan";
import TeamsSpaces from "@/components/WorkSpaces";
import LandingPage from "@/components/LandingPage";
import Header from "@/components/Header";
import { uploadAPI, utils } from "@/lib/api";

export default function FileQLanding() {
  // Authentication state
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [currentView, setCurrentView] = useState("teams"); // 'landing' or 'dashboard'

  // File upload state
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [downloadUrl, setDownloadUrl] = useState("");
  const [fileInfo, setFileInfo] = useState(null);
  const [error, setError] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);
  const [notifications, setNotifications] = useState([
    {
      id: 1,
      type: "warning",
      title: "Email Verification Required",
      message: "Please verify your email to access all features",
      time: "2 hours ago",
      unread: true,
    },
    {
      id: 2,
      type: "info",
      title: "Storage Almost Full",
      message: "You've used 4.2GB of your 5GB storage limit",
      time: "1 day ago",
      unread: true,
    },
    {
      id: 3,
      type: "success",
      title: "Team Invitation Sent",
      message: "Invitation sent to sarah@company.com",
      time: "2 days ago",
      unread: false,
    },
  ]);
  const [showNotifications, setShowNotifications] = useState(false);

  // Check authentication status on component mount
  useEffect(() => {
    const token = utils.getAuthToken();
    if (token) {
      setIsAuthenticated(true);
      // In a real app, you'd fetch user data from the API
      setUser({
        name: localStorage.getItem("user_name") || "User",
        email: localStorage.getItem("user_email") || "user@example.com",
      });
      // Redirect to dashboard if authenticated
      setCurrentView("settings");
    }
  }, []);

  // Handle successful authentication
  const handleAuthSuccess = (userData) => {
    setIsAuthenticated(true);
    setUser(userData);
    setCurrentView("dashboard");

    // Store user data in localStorage
    if (userData.name) localStorage.setItem("user_name", userData.name);
    if (userData.email) localStorage.setItem("user_email", userData.email);
  };

  // Handle logout
  const handleLogout = () => {
    utils.removeAuthToken();
    localStorage.removeItem("user_name");
    localStorage.removeItem("user_email");
    setIsAuthenticated(false);
    setUser(null);
    setCurrentView("landing");
    // Reset file upload state
    resetUpload();
  };

  // File handling functions
  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = async (file) => {
    setError("");
    setFileInfo({
      name: file.name,
      size: file.size,
      type: file.type,
      lastModified: file.lastModified,
    });

    try {
      setUploading(true);
      setUploadProgress(0);

      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + Math.random() * 15;
        });
      }, 200);

      const result = await uploadAPI.uploadFile(file);

      clearInterval(progressInterval);
      setUploadProgress(100);
      setDownloadUrl(result.download_url);
    } catch (err) {
      setError(
        err.message === "File too large"
          ? "File too large (3GB max). Please use FileQ CLI for larger files."
          : "Upload failed. Please try again."
      );
    } finally {
      setUploading(false);
    }
  };

  const resetUpload = () => {
    setDownloadUrl("");
    setFileInfo(null);
    setUploadProgress(0);
    setError("");
  };

  const handleToolClick = (toolId) => {
    const url = `/tools/${toolId}?file=${encodeURIComponent(downloadUrl)}`;
    console.log(`Navigate to ${url}`);
    // In real app: navigate(url);
  };

  const renderCurrentView = () => {
    switch (currentView) {
      case "dashboard":
        return (
          <Dashboard
            user={user}
            onLogout={handleLogout}
            onBackToLanding={() => setCurrentView("landing")}
          />
        );
      case "files":
        console.log(currentView, isAuthenticated);
        return <FileManager />;
      case "settings":
        return <Settings user={user} setUser={setUser} />;
      case "upgrade":
        return <UpgradePlan />;
      case "teams":
        return <TeamsSpaces />;
      default:
        return (
          <LandingPage
            isAuthenticated={isAuthenticated}
            user={user}
            onAuthSuccess={handleAuthSuccess}
            onLogout={handleLogout}
            onDashboardClick={() => setCurrentView("dashboard")}
          />
        );
    }
  };

  if (!isAuthenticated) {
    return (
      <LandingPage
        isAuthenticated={isAuthenticated}
        user={user}
        onAuthSuccess={handleAuthSuccess}
        onLogout={handleLogout}
        onDashboardClick={() => setCurrentView("dashboard")}
      />
    );
  }
  // Show landing page (default view)
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      {/* Header with Navigation */}
      {isAuthenticated && (
        <Header
          user={user}
          currentView={currentView}
          setCurrentView={setCurrentView}
          notifications={notifications}
          setNotifications={setNotifications}
          showNotifications={showNotifications}
          setShowNotifications={setShowNotifications}
          onLogout={handleLogout}
        />
      )}

      {/* Main Content */}
      {renderCurrentView()}
    </div>
  );
}
