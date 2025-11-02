import React, { useState, useRef } from "react";

// Import existing components (these would be imported from their respective files)

import Navigation from "@/components/Navigation";
import HeroSection from "@/components/HeroSection";
import UploadSection from "@/components/UploadSection";
import FileDetailsSection from "@/components/FileDetailsSection";
import ToolsGrid from "@/components/ToolsGrid";
import FeatureHighlights from "@/components/FeatureHighlights";
import DeveloperSection from "@/components/DeveloperSection";
import PricingSection from "@/components/PricingSection";
import Footer from "@/components/FooterSection";
import { uploadAPI, utils } from "@/lib/api";

export default function LandingPage({
  isAuthenticated,
  user,
  onAuthSuccess,
  onLogout,
  onDashboardClick,
}) {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [fileInfo, setFileInfo] = useState(null);
  const [error, setError] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState("");
  const inputRef = useRef(null);

  // Handle drag events
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  // Handle drop
  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  // Handle file selection
  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0]);
    }
  };

  // Handle file upload
  const handleFileUpload = async (file) => {
    setError("");
    setUploading(true);
    setUploadProgress(0);

    const info = {
      name: file.name,
      size: file.size,
      type: file.type,
      lastModified: new Date(file.lastModified),
    };
    setFileInfo(info);

    // Simulate upload progress
    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return prev;
        }
        return prev + Math.random() * 15;
      });
    }, 200);

    // Simulate upload completion
    setTimeout(() => {
      clearInterval(progressInterval);
      setUploadProgress(100);
      setUploading(false);
      setDownloadUrl(
        `https://fileq.com/d/${Math.random().toString(36).substr(2, 9)}`
      );
    }, 2000);
  };

  // Reset upload
  const resetUpload = () => {
    setFileInfo(null);
    setDownloadUrl("");
    setUploadProgress(0);
    setError("");
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  // Handle tool click
  const handleToolClick = (tool) => {
    console.log(`Tool clicked: ${tool}`);
    // Implement tool-specific logic here
  };

  // Show landing page (default view)
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      {!isAuthenticated && (
        <Navigation
          isAuthenticated={isAuthenticated}
          user={user}
          onAuthSuccess={onAuthSuccess}
          onLogout={onLogout}
          onDashboardClick={() => onDashboardClick("dashboard")}
        />
      )}

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        {!downloadUrl ? (
          // Pre-upload state
          <>
            <HeroSection />
            <UploadSection
              uploading={uploading}
              uploadProgress={uploadProgress}
              fileInfo={fileInfo}
              error={error}
              dragActive={dragActive}
              inputRef={inputRef}
              onDrag={handleDrag}
              onDrop={handleDrop}
              onFileSelect={handleFileSelect}
            />
            <FeatureHighlights />
          </>
        ) : (
          // Post-upload state - Split layout
          <div className="grid lg:grid-cols-2 gap-12 items-start">
            <FileDetailsSection
              fileInfo={fileInfo}
              downloadUrl={downloadUrl}
              onReset={resetUpload}
            />
            <ToolsGrid fileInfo={fileInfo} onToolClick={handleToolClick} />
          </div>
        )}
      </div>

      <DeveloperSection />
      <PricingSection />
      <Footer />
    </div>
  );
}
