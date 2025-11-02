// components/HeroSection.jsx
import React, { useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Upload,
  Share2,
  Download,
  Link,
  Users,
  Shield,
  Clock,
  Copy,
  Check,
  Scissors,
  Merge,
  Maximize,
  Crop,
  Sparkles,
  RefreshCw,
  FileText,
  VolumeX,
  Subtitles,
  Lock,
  Archive,
} from "lucide-react";

export default function HeroSection() {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploaded, setUploaded] = useState(false);
  const [fileInfo, setFileInfo] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);

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
    setFileInfo({
      name: file.name,
      size: file.size,
      type: file.type,
    });

    setUploading(true);
    setUploadProgress(0);

    // Simulate upload progress
    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 95) {
          clearInterval(progressInterval);
          return 95;
        }
        return prev + Math.random() * 20;
      });
    }, 150);

    // Simulate upload completion
    setTimeout(() => {
      clearInterval(progressInterval);
      setUploadProgress(100);
      setDownloadUrl(
        `https://fileq.com/share/${Math.random().toString(36).substr(2, 9)}`
      );
      setUploading(false);
      setUploaded(true);
    }, 2000);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(downloadUrl);
  };

  const resetDemo = () => {
    setUploaded(false);
    setUploading(false);
    setUploadProgress(0);
    setFileInfo(null);
    setDownloadUrl("");
  };

  const getFileTypeCategory = (mimeType) => {
    if (!mimeType) return "document";
    if (mimeType.includes("pdf")) return "pdf";
    if (mimeType.startsWith("image/")) return "image";
    if (mimeType.startsWith("audio/")) return "audio";
    if (mimeType.startsWith("video/")) return "video";
    return "document";
  };

  const getToolsForFileType = (mimeType) => {
    const commonTools = [
      { name: "Share", icon: Share2, color: "bg-blue-50 text-blue-600" },
      { name: "Download", icon: Download, color: "bg-green-50 text-green-600" },
      { name: "Encrypt", icon: Lock, color: "bg-slate-50 text-slate-600" },
    ];

    const typeSpecificTools = {
      pdf: [
        { name: "Merge PDFs", icon: Merge, color: "bg-red-50 text-red-600" },
        { name: "Split PDF", icon: Scissors, color: "bg-red-50 text-red-600" },
        { name: "Compress", icon: Archive, color: "bg-red-50 text-red-600" },
      ],
      image: [
        {
          name: "Resize",
          icon: Maximize,
          color: "bg-purple-50 text-purple-600",
        },
        { name: "Crop", icon: Crop, color: "bg-purple-50 text-purple-600" },
        {
          name: "Enhance",
          icon: Sparkles,
          color: "bg-purple-50 text-purple-600",
        },
        {
          name: "Convert",
          icon: RefreshCw,
          color: "bg-purple-50 text-purple-600",
        },
      ],
      audio: [
        {
          name: "Transcribe",
          icon: FileText,
          color: "bg-green-50 text-green-600",
        },
        {
          name: "Trim Audio",
          icon: Scissors,
          color: "bg-green-50 text-green-600",
        },
        {
          name: "Convert",
          icon: RefreshCw,
          color: "bg-green-50 text-green-600",
        },
      ],
      video: [
        {
          name: "Subtitles",
          icon: Subtitles,
          color: "bg-orange-50 text-orange-600",
        },
        {
          name: "Trim Video",
          icon: Scissors,
          color: "bg-orange-50 text-orange-600",
        },
        {
          name: "Extract Audio",
          icon: VolumeX,
          color: "bg-orange-50 text-orange-600",
        },
      ],
    };

    const category = getFileTypeCategory(mimeType);
    const specificTools = typeSpecificTools[category] || [];
    return [...commonTools, ...specificTools];
  };

  return (
    <div className="grid lg:grid-cols-2 gap-16 items-start mb-20">
      {/* Left Side - Marketing Content */}
      <div className="space-y-8">
        <h1 className="text-5xl lg:text-6xl font-bold text-slate-900 leading-tight">
          Upload & Share
          <span className="bg-gradient-to-r from-indigo-600 via-purple-600 to-cyan-600 bg-clip-text text-transparent block mt-2">
            Files Instantly
          </span>
        </h1>

        <p className="text-xl text-slate-600 leading-relaxed">
          Upload any file, get an instant shareable link, and access powerful
          processing tools. No signup required for basic uploads. Secure, fast,
          and simple.
        </p>

        <div className="space-y-4">
          <div className="flex items-center space-x-3 text-slate-700">
            <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
              <Upload className="w-4 h-4 text-green-600" />
            </div>
            <span className="font-medium">Drag & drop or click to upload</span>
          </div>
          <div className="flex items-center space-x-3 text-slate-700">
            <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
              <Share2 className="w-4 h-4 text-blue-600" />
            </div>
            <span className="font-medium">Get instant shareable links</span>
          </div>
          <div className="flex items-center space-x-3 text-slate-700">
            <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center">
              <Download className="w-4 h-4 text-purple-600" />
            </div>
            <span className="font-medium">Access powerful file tools</span>
          </div>
        </div>

        {/* Trust Indicators */}
        <div className="flex items-center space-x-6 text-slate-500 pt-4 text-sm">
          <div className="flex items-center space-x-2">
            <Users className="w-4 h-4" />
            <span>50k+ files uploaded daily</span>
          </div>
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4" />
            <span>Secure & encrypted</span>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-2 gap-4 pt-4">
          <div className="bg-white rounded-lg p-4 shadow-sm border border-slate-200 text-center">
            <div className="text-2xl font-bold text-indigo-600">3GB</div>
            <div className="text-sm text-slate-600">Max file size</div>
          </div>
          <div className="bg-white rounded-lg p-4 shadow-sm border border-slate-200 text-center">
            <div className="text-2xl font-bold text-green-600">100+</div>
            <div className="text-sm text-slate-600">File formats</div>
          </div>
        </div>
      </div>

      {/* Right Side - Working Upload Demo */}
      <div className="space-y-6">
        {!uploaded ? (
          // Upload Interface
          <Card className="border-2 border-dashed border-indigo-200 bg-gradient-to-br from-indigo-50/50 to-purple-50/50">
            <CardContent className="p-8">
              <div
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-300 cursor-pointer ${
                  dragActive
                    ? "border-indigo-400 bg-indigo-100/50 scale-105"
                    : "border-indigo-300 hover:border-indigo-400 hover:bg-indigo-50/30"
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => !uploading && inputRef.current?.click()}
              >
                {!uploading ? (
                  <>
                    <div className="w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
                      <Upload className="w-8 h-8 text-white" />
                    </div>
                    <h3 className="text-xl font-bold text-slate-900 mb-2">
                      Drop files here
                    </h3>
                    <p className="text-slate-600 mb-6">
                      Try the demo! All formats • 3GB max
                    </p>
                    <Button className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-6 py-2">
                      Choose Files
                    </Button>
                    <input
                      ref={inputRef}
                      type="file"
                      className="hidden"
                      onChange={handleFileSelect}
                    />
                  </>
                ) : (
                  <div className="space-y-4">
                    <div className="w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto">
                      <Upload className="w-8 h-8 text-white animate-pulse" />
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-slate-900 mb-4">
                        Uploading {fileInfo?.name}...
                      </p>
                      <Progress value={uploadProgress} className="w-full h-3" />
                      <p className="text-slate-600 mt-2">
                        {Math.round(uploadProgress)}% complete
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ) : (
          // Upload Success + Sharing + Tools
          <>
            {/* Instant Sharing */}
            <Card className="bg-green-50 border-green-200">
              <CardContent className="p-6">
                <div className="flex items-center space-x-3 mb-4">
                  <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                    <Check className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900">
                      Upload Complete!
                    </h4>
                    <p className="text-sm text-slate-600">{fileInfo?.name}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="text-sm font-medium text-slate-600">
                    Shareable Link
                  </label>
                  <div className="flex gap-2">
                    <Input
                      value={downloadUrl}
                      readOnly
                      className="font-mono text-sm bg-white"
                    />
                    <Button
                      size="sm"
                      onClick={copyToClipboard}
                      variant="outline"
                      className="border-green-300"
                    >
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                  <div className="flex items-center space-x-4 text-sm text-slate-600">
                    <div className="flex items-center space-x-1">
                      <Clock className="w-4 h-4" />
                      <span>Expires in 3 days</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <Shield className="w-4 h-4" />
                      <span>Encrypted</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Available Tools */}
            <Card className="bg-white shadow-lg">
              <CardContent className="p-6">
                <h4 className="font-bold text-slate-900 mb-4">
                  Available Tools
                </h4>
                <div className="grid grid-cols-2 gap-3">
                  {getToolsForFileType(fileInfo?.type).map((tool, index) => {
                    const IconComponent = tool.icon;
                    return (
                      <div
                        key={index}
                        className={`${tool.color} rounded-lg p-3 text-center transition-all hover:scale-105 cursor-pointer`}
                      >
                        <IconComponent
                          className={`w-5 h-5 mx-auto mb-1 ${
                            tool.color.split(" ")[1]
                          }`}
                        />
                        <div className="text-xs font-medium">{tool.name}</div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Reset Demo */}
            <Button onClick={resetDemo} variant="outline" className="w-full">
              Try Another File
            </Button>
          </>
        )}

        {/* Call to Action */}
        {!uploaded && (
          <div className="bg-slate-900 rounded-xl p-6 text-white text-center">
            <p className="font-semibold mb-2">Ready to share your files?</p>
            <p className="text-slate-300 text-sm mb-3">
              Upload above and get your shareable link instantly
            </p>
            <div className="flex items-center justify-center space-x-2 text-sm text-slate-400">
              <span>👆</span>
              <span>Try the demo upload</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
