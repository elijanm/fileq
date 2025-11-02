// components/Dashboard.jsx - Fresh FileQ Dashboard
import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Files,
  Download,
  Globe,
  Users,
  TrendingUp,
  Clock,
  BarChart3,
  Activity,
  Search,
  Bell,
  Settings,
  Plus,
  ArrowUpRight,
  ArrowDownRight,
  FileText,
  Image,
  Video,
  Archive,
  Zap,
  Shield,
  Star,
  Calendar,
  Filter,
  Upload,
  Share2,
  Trash2,
  Eye,
  ChevronRight,
} from "lucide-react";

export default function Dashboard({ user, onLogout }) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [searchQuery, setSearchQuery] = useState("");
  const [timeFilter, setTimeFilter] = useState("7d");
  const [animateStats, setAnimateStats] = useState(false);

  // Update time every minute
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  // Trigger animations on load
  useEffect(() => {
    setTimeout(() => setAnimateStats(true), 500);
  }, []);

  // Mock data
  const stats = {
    totalFiles: 2847,
    totalDownloads: 12394,
    storageUsed: "4.2 GB",
    activeShares: 67,
    growthFiles: 18.5,
    growthDownloads: 24.7,
    growthShares: 12.3,
  };

  const recentFiles = [
    {
      name: "Q4-Report-2024.pdf",
      size: "2.4 MB",
      uploaded: "2 hours ago",
      type: "pdf",
      downloads: 45,
    },
    {
      name: "Brand-Guidelines.zip",
      size: "15.7 MB",
      uploaded: "5 hours ago",
      type: "archive",
      downloads: 23,
    },
    {
      name: "Product-Demo.mp4",
      size: "128 MB",
      uploaded: "1 day ago",
      type: "video",
      downloads: 156,
    },
    {
      name: "Logo-Collection.png",
      size: "890 KB",
      uploaded: "2 days ago",
      type: "image",
      downloads: 89,
    },
    {
      name: "Contract-Template.docx",
      size: "156 KB",
      uploaded: "3 days ago",
      type: "document",
      downloads: 67,
    },
  ];

  const countryData = [
    { country: "United States", flag: "🇺🇸", downloads: 4567, percentage: 37 },
    { country: "Germany", flag: "🇩🇪", downloads: 2890, percentage: 23 },
    { country: "United Kingdom", flag: "🇬🇧", downloads: 1845, percentage: 15 },
    { country: "Canada", flag: "🇨🇦", downloads: 1234, percentage: 10 },
    { country: "France", flag: "🇫🇷", downloads: 987, percentage: 8 },
    { country: "Others", flag: "🌍", downloads: 871, percentage: 7 },
  ];

  const fileTypeData = [
    { type: "PDFs", count: 1247, color: "#ef4444", icon: "📄" },
    { type: "Images", count: 856, color: "#10b981", icon: "🖼️" },
    { type: "Videos", count: 423, color: "#f59e0b", icon: "🎥" },
    { type: "Archives", count: 321, color: "#8b5cf6", icon: "📦" },
  ];

  const weeklyData = {
    labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    uploads: [15, 23, 18, 35, 42, 28, 19],
    downloads: [89, 134, 98, 167, 203, 156, 112],
  };

  // Animation counter hook
  function useCounter(end, duration = 2000, start = 0) {
    const [count, setCount] = useState(start);

    useEffect(() => {
      if (!animateStats) return;

      let startTime;
      const animate = (currentTime) => {
        if (!startTime) startTime = currentTime;
        const progress = Math.min((currentTime - startTime) / duration, 1);
        setCount(Math.floor(progress * (end - start) + start));
        if (progress < 1) requestAnimationFrame(animate);
      };
      requestAnimationFrame(animate);
    }, [end, duration, start, animateStats]);

    return count;
  }

  // Animated stat card component
  function StatCard({
    title,
    value,
    change,
    changeType,
    icon: Icon,
    delay = 0,
    suffix = "",
  }) {
    const animatedValue = useCounter(
      typeof value === "string" ? parseInt(value.replace(/[^\d]/g, "")) : value
    );
    const displayValue =
      typeof value === "string" && value.includes("GB")
        ? `${(animatedValue / 1000).toFixed(1)} GB`
        : animatedValue.toLocaleString() + suffix;

    return (
      <Card
        className={`group hover:shadow-xl transition-all duration-500 border-0 bg-white overflow-hidden hover:scale-105 transform ${
          animateStats ? "animate-slideUp" : ""
        }`}
        style={{ animationDelay: `${delay}ms` }}
      >
        <CardContent className="p-6 relative">
          {/* Background gradient on hover */}
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-cyan-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>

          <div className="relative flex items-center justify-between">
            <div className="flex-1">
              <div className="flex items-center space-x-3 mb-3">
                <div className="p-3 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl shadow-lg group-hover:scale-110 transition-transform duration-300">
                  <Icon className="w-6 h-6 text-white" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-600">{title}</p>
                  <p className="text-3xl font-bold text-slate-900">
                    {displayValue}
                  </p>
                </div>
              </div>
            </div>

            {change && (
              <div
                className={`flex items-center space-x-1 px-3 py-1 rounded-full text-sm font-semibold ${
                  changeType === "up"
                    ? "bg-green-100 text-green-700"
                    : "bg-red-100 text-red-700"
                }`}
              >
                {changeType === "up" ? (
                  <ArrowUpRight className="w-4 h-4" />
                ) : (
                  <ArrowDownRight className="w-4 h-4" />
                )}
                <span>+{change}%</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  // File type icon helper
  function getFileIcon(type) {
    const icons = {
      pdf: "📄",
      archive: "📦",
      video: "🎥",
      image: "🖼️",
      document: "📝",
    };
    return icons[type] || "📄";
  }

  // File size formatter
  function formatFileSize(size) {
    return size;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      {/* Header */}
      {/* <header className="bg-white/95 backdrop-blur-md border-b border-slate-200/60 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex justify-between items-center h-18 py-4">
           
            <div className="flex items-center space-x-6">
              <div className="flex items-center space-x-3">
                <div className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent">
                  FileQ
                </div>
                <div className="px-2 py-1 bg-blue-100 text-blue-600 text-xs rounded-full font-medium">
                  Dashboard
                </div>
              </div>

              
              <div className="hidden lg:flex items-center space-x-6 text-sm">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-slate-600">
                    All systems operational
                  </span>
                </div>
                <div className="text-slate-500">
                  {currentTime.toLocaleDateString("en-US", {
                    weekday: "long",
                    month: "short",
                    day: "numeric",
                  })}
                </div>
              </div>
            </div>

         
            <div className="flex items-center space-x-4">
         
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

            
              <Button variant="outline" size="sm" className="relative">
                <Bell className="w-4 h-4" />
                <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full"></div>
              </Button>

              
              <select
                value={timeFilter}
                onChange={(e) => setTimeFilter(e.target.value)}
                className="border border-slate-200 rounded-xl px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
                <option value="90d">Last 90 days</option>
              </select>

          
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
                  <div className="text-xs text-slate-500">Premium Plan</div>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={onLogout}
                  className="text-slate-600 hover:text-red-600 border-slate-200"
                >
                  Logout
                </Button>
              </div>
            </div>
          </div>
        </div>
      </header> */}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-slate-900 mb-3">
            Good{" "}
            {currentTime.getHours() < 12
              ? "morning"
              : currentTime.getHours() < 17
              ? "afternoon"
              : "evening"}
            , {user?.name || "User"}! 👋
          </h1>
          <p className="text-xl text-slate-600">
            Here's your file activity overview and recent statistics.
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Files"
            value={stats.totalFiles}
            change={stats.growthFiles}
            changeType="up"
            icon={Files}
            delay={100}
          />
          <StatCard
            title="Total Downloads"
            value={stats.totalDownloads}
            change={stats.growthDownloads}
            changeType="up"
            icon={Download}
            delay={200}
          />
          <StatCard
            title="Storage Used"
            value="4200"
            suffix=" MB"
            icon={Shield}
            delay={300}
          />
          <StatCard
            title="Active Shares"
            value={stats.activeShares}
            change={stats.growthShares}
            changeType="up"
            icon={Share2}
            delay={400}
          />
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
          {/* Weekly Activity Chart */}
          <div className="lg:col-span-2">
            <Card className="border-0 shadow-lg bg-white h-full">
              <CardHeader className="pb-4">
                <div className="flex justify-between items-center">
                  <CardTitle className="text-xl font-bold text-slate-900 flex items-center">
                    <BarChart3 className="w-6 h-6 mr-3 text-blue-600" />
                    Weekly Activity
                  </CardTitle>
                  <div className="flex items-center space-x-4 text-sm">
                    <div className="flex items-center">
                      <div className="w-3 h-3 bg-blue-500 rounded-full mr-2"></div>
                      <span>Uploads</span>
                    </div>
                    <div className="flex items-center">
                      <div className="w-3 h-3 bg-cyan-500 rounded-full mr-2"></div>
                      <span>Downloads</span>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="h-80 flex items-end justify-between px-4 pb-4 space-x-2">
                  {weeklyData.labels.map((day, index) => {
                    const maxValue = Math.max(...weeklyData.downloads);
                    const uploadHeight =
                      (weeklyData.uploads[index] / maxValue) * 200;
                    const downloadHeight =
                      (weeklyData.downloads[index] / maxValue) * 200;

                    return (
                      <div
                        key={day}
                        className="flex flex-col items-center flex-1 space-y-2"
                      >
                        <div className="flex flex-col items-center space-y-1 w-full">
                          {/* Download bar */}
                          <div
                            className="w-full bg-gradient-to-t from-cyan-500 to-cyan-400 rounded-t-lg transition-all duration-1000 hover:scale-105 cursor-pointer group relative"
                            style={{
                              height: `${downloadHeight}px`,
                              animationDelay: `${index * 100}ms`,
                            }}
                          >
                            <div className="absolute -top-8 left-1/2 transform -translate-x-1/2 bg-slate-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                              {weeklyData.downloads[index]} downloads
                            </div>
                          </div>

                          {/* Upload bar */}
                          <div
                            className="w-full bg-gradient-to-t from-blue-500 to-blue-400 rounded-t-lg transition-all duration-1000 hover:scale-105 cursor-pointer group relative"
                            style={{
                              height: `${uploadHeight}px`,
                              animationDelay: `${index * 100 + 50}ms`,
                            }}
                          >
                            <div className="absolute -top-8 left-1/2 transform -translate-x-1/2 bg-slate-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                              {weeklyData.uploads[index]} uploads
                            </div>
                          </div>
                        </div>
                        <span className="text-sm font-medium text-slate-600">
                          {day}
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* Totals */}
                <div className="grid grid-cols-2 gap-4 mt-6 pt-6 border-t border-slate-100">
                  <div className="text-center p-4 bg-blue-50 rounded-xl">
                    <div className="text-2xl font-bold text-blue-600">
                      {weeklyData.uploads.reduce((a, b) => a + b, 0)}
                    </div>
                    <div className="text-sm text-blue-600 font-medium">
                      Total Uploads
                    </div>
                  </div>
                  <div className="text-center p-4 bg-cyan-50 rounded-xl">
                    <div className="text-2xl font-bold text-cyan-600">
                      {weeklyData.downloads.reduce((a, b) => a + b, 0)}
                    </div>
                    <div className="text-sm text-cyan-600 font-medium">
                      Total Downloads
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Downloads by Country */}
          <div>
            <Card className="border-0 shadow-lg bg-white h-full">
              <CardHeader className="pb-4">
                <CardTitle className="text-xl font-bold text-slate-900 flex items-center">
                  <Globe className="w-6 h-6 mr-3 text-blue-600" />
                  Top Countries
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {countryData.map((country, index) => (
                  <div
                    key={country.country}
                    className="flex items-center space-x-4 p-3 rounded-lg hover:bg-slate-50 transition-all duration-300 cursor-pointer group"
                    style={{ animationDelay: `${index * 100}ms` }}
                  >
                    <span className="text-2xl group-hover:scale-110 transition-transform">
                      {country.flag}
                    </span>
                    <div className="flex-1">
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-semibold text-slate-800">
                          {country.country}
                        </span>
                        <span className="text-sm text-slate-500 font-medium">
                          {country.downloads.toLocaleString()}
                        </span>
                      </div>
                      <div className="w-full bg-slate-200 rounded-full h-2">
                        <div
                          className="bg-gradient-to-r from-blue-500 to-cyan-500 h-2 rounded-full transition-all duration-1000 group-hover:shadow-lg"
                          style={{
                            width: `${country.percentage}%`,
                            animationDelay: `${index * 150}ms`,
                          }}
                        ></div>
                      </div>
                    </div>
                    <span className="text-sm font-bold text-slate-600 min-w-[35px]">
                      {country.percentage}%
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Bottom Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Recent Files */}
          <Card className="border-0 shadow-lg bg-white">
            <CardHeader className="pb-4">
              <div className="flex justify-between items-center">
                <CardTitle className="text-xl font-bold text-slate-900 flex items-center">
                  <Clock className="w-6 h-6 mr-3 text-blue-600" />
                  Recent Files
                </CardTitle>
                <Button variant="outline" size="sm" className="text-blue-600">
                  View All
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              {recentFiles.map((file, index) => (
                <div
                  key={file.name}
                  className="flex items-center space-x-4 p-4 rounded-lg hover:bg-slate-50 transition-all duration-300 cursor-pointer group"
                  style={{ animationDelay: `${index * 80}ms` }}
                >
                  <div className="text-2xl group-hover:scale-110 transition-transform">
                    {getFileIcon(file.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-slate-900 truncate group-hover:text-blue-600 transition-colors">
                      {file.name}
                    </p>
                    <div className="flex items-center space-x-4 text-sm text-slate-500">
                      <span>{formatFileSize(file.size)}</span>
                      <span>•</span>
                      <span>{file.uploaded}</span>
                      <span>•</span>
                      <span className="flex items-center">
                        <Download className="w-3 h-3 mr-1" />
                        {file.downloads}
                      </span>
                    </div>
                  </div>
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity flex space-x-2">
                    <Button variant="ghost" size="sm">
                      <Eye className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Share2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* File Types */}
          <Card className="border-0 shadow-lg bg-white">
            <CardHeader className="pb-4">
              <CardTitle className="text-xl font-bold text-slate-900 flex items-center">
                <Activity className="w-6 h-6 mr-3 text-blue-600" />
                File Types
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {fileTypeData.map((fileType, index) => {
                const maxCount = Math.max(...fileTypeData.map((f) => f.count));
                const percentage = (fileType.count / maxCount) * 100;

                return (
                  <div
                    key={fileType.type}
                    className="group cursor-pointer"
                    style={{ animationDelay: `${index * 100}ms` }}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        <span className="text-xl group-hover:scale-110 transition-transform">
                          {fileType.icon}
                        </span>
                        <span className="font-semibold text-slate-800 group-hover:text-blue-600 transition-colors">
                          {fileType.type}
                        </span>
                      </div>
                      <div className="text-right">
                        <div className="font-bold text-slate-900">
                          {fileType.count.toLocaleString()}
                        </div>
                        <div className="text-sm text-slate-500">files</div>
                      </div>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-3">
                      <div
                        className="h-3 rounded-full transition-all duration-1000 group-hover:shadow-md"
                        style={{
                          width: `${percentage}%`,
                          backgroundColor: fileType.color,
                          animationDelay: `${index * 150}ms`,
                        }}
                      ></div>
                    </div>
                  </div>
                );
              })}

              {/* Quick Actions */}
              <div className="pt-6 border-t border-slate-100">
                <div className="grid grid-cols-2 gap-3">
                  <Button className="bg-gradient-to-r from-blue-500 to-cyan-500 text-white">
                    <Upload className="w-4 h-4 mr-2" />
                    Upload
                  </Button>
                  <Button variant="outline">
                    <Plus className="w-4 h-4 mr-2" />
                    Create
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>

      {/* Custom CSS for animations */}
      <style jsx>{`
        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(30px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .animate-slideUp {
          animation: slideUp 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
          opacity: 0;
        }

        /* Custom scrollbar */
        ::-webkit-scrollbar {
          width: 6px;
        }

        ::-webkit-scrollbar-track {
          background: #f1f5f9;
        }

        ::-webkit-scrollbar-thumb {
          background: #cbd5e1;
          border-radius: 3px;
        }

        ::-webkit-scrollbar-thumb:hover {
          background: #94a3b8;
        }
      `}</style>
    </div>
  );
}
