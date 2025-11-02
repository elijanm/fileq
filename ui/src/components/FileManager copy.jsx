// components/FileManager.jsx - Complete File Management Dashboard
import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Files,
  Search,
  Filter,
  Grid3X3,
  List,
  Plus,
  FolderPlus,
  Upload,
  MoreVertical,
  Eye,
  Download,
  Share2,
  Copy,
  Move,
  Trash2,
  Star,
  Clock,
  FileText,
  Image,
  Video,
  Archive,
  File,
  Folder,
  ChevronRight,
  ChevronDown,
  X,
  Check,
  SortAsc,
  SortDesc,
  Calendar,
  User,
  HardDrive,
  Tag,
  ArrowLeft,
  RefreshCw,
  Settings,
  Edit3,
  Info,
  Lock,
  Unlock,
  Link,
} from "lucide-react";

export default function FileManager({ user, onBack }) {
  // View and filter states
  const [viewMode, setViewMode] = useState("grid"); // 'grid' or 'list'
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [sortBy, setSortBy] = useState("name");
  const [sortOrder, setSortOrder] = useState("asc");
  const [filterType, setFilterType] = useState("all");
  const [filterDate, setFilterDate] = useState("all");
  const [filterSize, setFilterSize] = useState("all");
  const [currentFolder, setCurrentFolder] = useState("/");
  const [showFilters, setShowFilters] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Modal states
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [showMoveModal, setShowMoveModal] = useState(false);
  const [showCopyModal, setShowCopyModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [selectedDestination, setSelectedDestination] = useState("/");

  // Mock data - replace with real API calls
  const [files, setFiles] = useState([
    {
      id: "1",
      name: "Q4-Report-2024.pdf",
      type: "pdf",
      size: "2.4 MB",
      sizeBytes: 2400000,
      modified: "2024-09-22T10:30:00Z",
      owner: "John Doe",
      folder: "/",
      starred: true,
      shared: false,
      downloads: 45,
      thumbnail: null,
    },
    {
      id: "2",
      name: "Brand Guidelines",
      type: "folder",
      size: "15 items",
      sizeBytes: 0,
      modified: "2024-09-20T14:22:00Z",
      owner: "Sarah Wilson",
      folder: "/",
      starred: false,
      shared: true,
      downloads: 0,
      thumbnail: null,
    },
    {
      id: "3",
      name: "Product-Demo.mp4",
      type: "video",
      size: "128 MB",
      sizeBytes: 128000000,
      modified: "2024-09-21T16:45:00Z",
      owner: "Mike Johnson",
      folder: "/",
      starred: false,
      shared: true,
      downloads: 156,
      thumbnail: "/thumbnails/video-thumb.jpg",
    },
    {
      id: "4",
      name: "Logo-Collection.zip",
      type: "archive",
      size: "890 KB",
      sizeBytes: 890000,
      modified: "2024-09-19T09:12:00Z",
      owner: "Design Team",
      folder: "/",
      starred: false,
      shared: false,
      downloads: 23,
      thumbnail: null,
    },
    {
      id: "5",
      name: "Contract-Template.docx",
      type: "document",
      size: "156 KB",
      sizeBytes: 156000,
      modified: "2024-09-18T11:30:00Z",
      owner: "Legal Team",
      folder: "/",
      starred: true,
      shared: true,
      downloads: 67,
      thumbnail: null,
    },
    {
      id: "6",
      name: "Marketing Assets",
      type: "folder",
      size: "8 items",
      sizeBytes: 0,
      modified: "2024-09-17T13:20:00Z",
      owner: "Marketing Team",
      folder: "/",
      starred: false,
      shared: false,
      downloads: 0,
      thumbnail: null,
    },
  ]);

  const folders = [
    { id: "root", name: "/", path: "/", parent: null },
    {
      id: "brand",
      name: "Brand Guidelines",
      path: "/Brand Guidelines",
      parent: "root",
    },
    {
      id: "marketing",
      name: "Marketing Assets",
      path: "/Marketing Assets",
      parent: "root",
    },
    {
      id: "legal",
      name: "Legal Documents",
      path: "/Legal Documents",
      parent: "root",
    },
    { id: "projects", name: "Projects", path: "/Projects", parent: "root" },
  ];

  // File type icons and colors
  const getFileIcon = (type) => {
    const icons = {
      folder: { icon: Folder, color: "#3b82f6", bg: "#dbeafe" },
      pdf: { icon: FileText, color: "#dc2626", bg: "#fecaca" },
      image: { icon: Image, color: "#059669", bg: "#a7f3d0" },
      video: { icon: Video, color: "#d97706", bg: "#fed7aa" },
      archive: { icon: Archive, color: "#7c3aed", bg: "#ddd6fe" },
      document: { icon: File, color: "#0891b2", bg: "#a5f3fc" },
      default: { icon: File, color: "#6b7280", bg: "#f3f4f6" },
    };
    return icons[type] || icons.default;
  };

  // Format file size
  const formatFileSize = (bytes) => {
    if (bytes === 0 || isNaN(bytes)) return "0 KB";
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + " " + sizes[i];
  };

  // Format date
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 1) return "Today";
    if (diffDays === 2) return "Yesterday";
    if (diffDays <= 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
  };

  // Filter and sort files
  const filteredFiles = files
    .filter((file) => {
      // Search filter
      if (
        searchQuery &&
        !file.name.toLowerCase().includes(searchQuery.toLowerCase())
      ) {
        return false;
      }

      // Type filter
      if (filterType !== "all" && file.type !== filterType) {
        return false;
      }

      // Date filter
      if (filterDate !== "all") {
        const fileDate = new Date(file.modified);
        const now = new Date();
        const diffDays = Math.ceil((now - fileDate) / (1000 * 60 * 60 * 24));

        if (filterDate === "today" && diffDays > 1) return false;
        if (filterDate === "week" && diffDays > 7) return false;
        if (filterDate === "month" && diffDays > 30) return false;
      }

      // Size filter
      if (filterSize !== "all") {
        if (filterSize === "small" && file.sizeBytes > 1000000) return false;
        if (
          filterSize === "medium" &&
          (file.sizeBytes <= 1000000 || file.sizeBytes > 100000000)
        )
          return false;
        if (filterSize === "large" && file.sizeBytes <= 100000000) return false;
      }

      return file.folder === currentFolder;
    })
    .sort((a, b) => {
      let aValue = a[sortBy];
      let bValue = b[sortBy];

      // Sort folders first
      if (a.type === "folder" && b.type !== "folder") return -1;
      if (a.type !== "folder" && b.type === "folder") return 1;

      if (sortBy === "size") {
        aValue = a.sizeBytes;
        bValue = b.sizeBytes;
      } else if (sortBy === "modified") {
        aValue = new Date(a.modified);
        bValue = new Date(b.modified);
      }

      if (typeof aValue === "string") {
        aValue = aValue.toLowerCase();
        bValue = bValue.toLowerCase();
      }

      const result = aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      return sortOrder === "asc" ? result : -result;
    });

  // File selection handlers
  const handleFileSelect = (fileId) => {
    const newSelected = new Set(selectedFiles);
    if (newSelected.has(fileId)) {
      newSelected.delete(fileId);
    } else {
      newSelected.add(fileId);
    }
    setSelectedFiles(newSelected);
  };

  const selectAll = () => {
    if (selectedFiles.size === filteredFiles.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(filteredFiles.map((f) => f.id)));
    }
  };

  // File operations
  const handleCreateFolder = () => {
    if (!newFolderName.trim()) return;

    const newFolder = {
      id: Date.now().toString(),
      name: newFolderName,
      type: "folder",
      size: "0 items",
      sizeBytes: 0,
      modified: new Date().toISOString(),
      owner: user?.name || "You",
      folder: currentFolder,
      starred: false,
      shared: false,
      downloads: 0,
      thumbnail: null,
    };

    setFiles([...files, newFolder]);
    setNewFolderName("");
    setShowCreateFolder(false);
  };

  const handleDeleteFiles = () => {
    setFiles(files.filter((file) => !selectedFiles.has(file.id)));
    setSelectedFiles(new Set());
    setShowDeleteModal(false);
  };

  const handleStarToggle = (fileId) => {
    setFiles(
      files.map((file) =>
        file.id === fileId ? { ...file, starred: !file.starred } : file
      )
    );
  };

  // Breadcrumb component
  const Breadcrumb = () => {
    const pathParts = currentFolder.split("/").filter(Boolean);

    return (
      <nav className="flex items-center space-x-2 text-sm">
        <button
          onClick={() => setCurrentFolder("/")}
          className="text-blue-600 hover:text-blue-700 font-medium"
        >
          Home
        </button>
        {pathParts.map((part, index) => (
          <React.Fragment key={index}>
            <ChevronRight className="w-4 h-4 text-slate-400" />
            <button
              onClick={() =>
                setCurrentFolder("/" + pathParts.slice(0, index + 1).join("/"))
              }
              className="text-blue-600 hover:text-blue-700 font-medium"
            >
              {part}
            </button>
          </React.Fragment>
        ))}
      </nav>
    );
  };

  // File card component for grid view
  const FileCard = ({ file }) => {
    const { icon: Icon, color, bg } = getFileIcon(file.type);
    const isSelected = selectedFiles.has(file.id);

    return (
      <Card
        className={`group cursor-pointer transition-all duration-200 hover:shadow-lg hover:-translate-y-1 ${
          isSelected ? "ring-2 ring-blue-500 shadow-lg" : ""
        }`}
        onClick={() => handleFileSelect(file.id)}
      >
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div
              className="p-3 rounded-xl group-hover:scale-110 transition-transform"
              style={{ backgroundColor: bg }}
            >
              <Icon className="w-6 h-6" style={{ color }} />
            </div>
            <div className="flex items-center space-x-1">
              {file.starred && (
                <Star className="w-4 h-4 text-yellow-500 fill-current" />
              )}
              {file.shared && <Share2 className="w-4 h-4 text-green-500" />}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  // Show context menu
                }}
                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-slate-100 rounded"
              >
                <MoreVertical className="w-4 h-4 text-slate-500" />
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="font-semibold text-slate-900 truncate group-hover:text-blue-600 transition-colors">
              {file.name}
            </h3>
            <div className="flex items-center justify-between text-sm text-slate-500">
              <span>{file.size}</span>
              <span>{formatDate(file.modified)}</span>
            </div>
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>{file.owner}</span>
              {file.type !== "folder" && (
                <span className="flex items-center">
                  <Download className="w-3 h-3 mr-1" />
                  {file.downloads}
                </span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  // File row component for list view
  const FileRow = ({ file }) => {
    const { icon: Icon, color } = getFileIcon(file.type);
    const isSelected = selectedFiles.has(file.id);

    return (
      <tr
        className={`hover:bg-slate-50 cursor-pointer transition-colors ${
          isSelected ? "bg-blue-50" : ""
        }`}
        onClick={() => handleFileSelect(file.id)}
      >
        <td className="px-6 py-4">
          <div className="flex items-center space-x-3">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => {}}
              className="rounded border-slate-300"
              onClick={(e) => e.stopPropagation()}
            />
            <div className="flex items-center space-x-3">
              <Icon className="w-5 h-5" style={{ color }} />
              <div>
                <div className="font-medium text-slate-900">{file.name}</div>
                {file.type === "folder" && (
                  <div className="text-xs text-slate-500">{file.size}</div>
                )}
              </div>
            </div>
          </div>
        </td>
        <td className="px-6 py-4 text-sm text-slate-500">
          {file.type !== "folder" ? file.size : "—"}
        </td>
        <td className="px-6 py-4 text-sm text-slate-500">
          {formatDate(file.modified)}
        </td>
        <td className="px-6 py-4 text-sm text-slate-500">{file.owner}</td>
        <td className="px-6 py-4 text-sm text-slate-500">
          {file.type !== "folder" ? file.downloads : "—"}
        </td>
        <td className="px-6 py-4">
          <div className="flex items-center space-x-2">
            {file.starred && (
              <Star className="w-4 h-4 text-yellow-500 fill-current" />
            )}
            {file.shared && <Share2 className="w-4 h-4 text-green-500" />}
            <button
              onClick={(e) => {
                e.stopPropagation();
                // Show context menu
              }}
              className="p-1 hover:bg-slate-100 rounded"
            >
              <MoreVertical className="w-4 h-4 text-slate-500" />
            </button>
          </div>
        </td>
      </tr>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      {/* Header */}
      <header className="bg-white/95 backdrop-blur-md border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Left side */}
            <div className="flex items-center space-x-4">
              <Button
                variant="ghost"
                onClick={onBack}
                className="flex items-center text-slate-600 hover:text-blue-600"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Dashboard
              </Button>

              <div className="w-px h-6 bg-slate-300"></div>

              <div className="flex items-center space-x-2">
                <Files className="w-5 h-5 text-blue-600" />
                <h1 className="text-xl font-bold text-slate-900">
                  File Manager
                </h1>
              </div>
            </div>

            {/* Right side */}
            <div className="flex items-center space-x-4">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search files..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-4 py-2 w-64 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                />
              </div>

              {/* View toggle */}
              <div className="flex items-center border border-slate-200 rounded-lg p-1">
                <button
                  onClick={() => setViewMode("grid")}
                  className={`p-2 rounded ${
                    viewMode === "grid"
                      ? "bg-blue-100 text-blue-600"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <Grid3X3 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setViewMode("list")}
                  className={`p-2 rounded ${
                    viewMode === "list"
                      ? "bg-blue-100 text-blue-600"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <List className="w-4 h-4" />
                </button>
              </div>

              {/* Actions */}
              <Button
                onClick={() => setShowCreateFolder(true)}
                variant="outline"
                className="flex items-center"
              >
                <FolderPlus className="w-4 h-4 mr-2" />
                New Folder
              </Button>

              <Button className="bg-blue-600 hover:bg-blue-700 flex items-center">
                <Upload className="w-4 h-4 mr-2" />
                Upload Files
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 lg:px-8 py-6">
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-6">
          {/* Breadcrumb */}
          <Breadcrumb />

          {/* Toolbar actions */}
          <div className="flex items-center space-x-4">
            {selectedFiles.size > 0 && (
              <div className="flex items-center space-x-2 px-4 py-2 bg-blue-50 border border-blue-200 rounded-lg">
                <span className="text-sm font-medium text-blue-700">
                  {selectedFiles.size} selected
                </span>
                <div className="flex items-center space-x-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setShowMoveModal(true)}
                  >
                    <Move className="w-4 h-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setShowCopyModal(true)}
                  >
                    <Copy className="w-4 h-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setShowDeleteModal(true)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}

            {/* Filters */}
            <Button
              variant="outline"
              onClick={() => setShowFilters(!showFilters)}
              className={showFilters ? "bg-blue-50 text-blue-600" : ""}
            >
              <Filter className="w-4 h-4 mr-2" />
              Filters
            </Button>

            {/* Sort */}
            <select
              value={`${sortBy}-${sortOrder}`}
              onChange={(e) => {
                const [field, order] = e.target.value.split("-");
                setSortBy(field);
                setSortOrder(order);
              }}
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm"
            >
              <option value="name-asc">Name A-Z</option>
              <option value="name-desc">Name Z-A</option>
              <option value="modified-desc">Newest First</option>
              <option value="modified-asc">Oldest First</option>
              <option value="size-desc">Largest First</option>
              <option value="size-asc">Smallest First</option>
            </select>

            <Button variant="ghost" onClick={() => setIsLoading(true)}>
              <RefreshCw
                className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`}
              />
            </Button>
          </div>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <Card className="mb-6 border-0 shadow-sm">
            <CardContent className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    File Type
                  </label>
                  <select
                    value={filterType}
                    onChange={(e) => setFilterType(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="all">All Types</option>
                    <option value="folder">Folders</option>
                    <option value="pdf">PDFs</option>
                    <option value="image">Images</option>
                    <option value="video">Videos</option>
                    <option value="archive">Archives</option>
                    <option value="document">Documents</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Modified
                  </label>
                  <select
                    value={filterDate}
                    onChange={(e) => setFilterDate(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="all">All Time</option>
                    <option value="today">Today</option>
                    <option value="week">This Week</option>
                    <option value="month">This Month</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    File Size
                  </label>
                  <select
                    value={filterSize}
                    onChange={(e) => setFilterSize(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="all">All Sizes</option>
                    <option value="small">Small (&lt; 1MB)</option>
                    <option value="medium">Medium (1MB - 100MB)</option>
                    <option value="large">Large (&gt; 100MB)</option>
                  </select>
                </div>

                <div className="flex items-end">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setFilterType("all");
                      setFilterDate("all");
                      setFilterSize("all");
                      setSearchQuery("");
                    }}
                    className="w-full"
                  >
                    Clear Filters
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Files Display */}
        {viewMode === "grid" ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filteredFiles.map((file) => (
              <FileCard key={file.id} file={file} />
            ))}
          </div>
        ) : (
          <Card className="border-0 shadow-sm">
            <CardContent className="p-0">
              <table className="w-full">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-6 py-3 text-left">
                      <div className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={
                            selectedFiles.size === filteredFiles.length &&
                            filteredFiles.length > 0
                          }
                          onChange={selectAll}
                          className="rounded border-slate-300"
                        />
                        <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                          Name
                        </span>
                      </div>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Size
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Modified
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Owner
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Downloads
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                  {filteredFiles.map((file) => (
                    <FileRow key={file.id} file={file} />
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}

        {/* Empty state */}
        {filteredFiles.length === 0 && (
          <div className="text-center py-12">
            <Files className="w-12 h-12 text-slate-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-900 mb-2">
              No files found
            </h3>
            <p className="text-slate-500 mb-6">
              {searchQuery ||
              filterType !== "all" ||
              filterDate !== "all" ||
              filterSize !== "all"
                ? "Try adjusting your filters or search query."
                : "Upload some files to get started."}
            </p>
            <Button className="bg-blue-600 hover:bg-blue-700">
              <Upload className="w-4 h-4 mr-2" />
              Upload Files
            </Button>
          </div>
        )}
      </main>

      {/* Create Folder Modal */}
      {showCreateFolder && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Create New Folder</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Folder Name
                </label>
                <input
                  type="text"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  placeholder="Enter folder name"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  autoFocus
                />
              </div>
              <div className="flex justify-end space-x-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowCreateFolder(false);
                    setNewFolderName("");
                  }}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreateFolder}
                  disabled={!newFolderName.trim()}
                >
                  Create Folder
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle className="flex items-center text-red-600">
                <Trash2 className="w-5 h-5 mr-2" />
                Delete Files
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-slate-600">
                Are you sure you want to delete {selectedFiles.size}{" "}
                {selectedFiles.size === 1 ? "file" : "files"}? This action
                cannot be undone.
              </p>
              <div className="flex justify-end space-x-2">
                <Button
                  variant="outline"
                  onClick={() => setShowDeleteModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleDeleteFiles}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  Delete
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Move Files Modal */}
      {showMoveModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle className="flex items-center">
                <Move className="w-5 h-5 mr-2 text-blue-600" />
                Move Files
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Select destination folder
                </label>
                <select
                  value={selectedDestination}
                  onChange={(e) => setSelectedDestination(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {folders.map((folder) => (
                    <option key={folder.id} value={folder.path}>
                      {folder.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="bg-blue-50 p-3 rounded-lg">
                <p className="text-sm text-blue-700">
                  Moving {selectedFiles.size}{" "}
                  {selectedFiles.size === 1 ? "file" : "files"} to:{" "}
                  {selectedDestination}
                </p>
              </div>
              <div className="flex justify-end space-x-2">
                <Button
                  variant="outline"
                  onClick={() => setShowMoveModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => {
                    // Handle move operation
                    setFiles(
                      files.map((file) =>
                        selectedFiles.has(file.id)
                          ? { ...file, folder: selectedDestination }
                          : file
                      )
                    );
                    setSelectedFiles(new Set());
                    setShowMoveModal(false);
                  }}
                >
                  Move Files
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Copy Files Modal */}
      {showCopyModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle className="flex items-center">
                <Copy className="w-5 h-5 mr-2 text-green-600" />
                Copy Files
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Select destination folder
                </label>
                <select
                  value={selectedDestination}
                  onChange={(e) => setSelectedDestination(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {folders.map((folder) => (
                    <option key={folder.id} value={folder.path}>
                      {folder.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="bg-green-50 p-3 rounded-lg">
                <p className="text-sm text-green-700">
                  Copying {selectedFiles.size}{" "}
                  {selectedFiles.size === 1 ? "file" : "files"} to:{" "}
                  {selectedDestination}
                </p>
              </div>
              <div className="flex justify-end space-x-2">
                <Button
                  variant="outline"
                  onClick={() => setShowCopyModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => {
                    // Handle copy operation
                    const filesToCopy = files.filter((file) =>
                      selectedFiles.has(file.id)
                    );
                    const copiedFiles = filesToCopy.map((file) => ({
                      ...file,
                      id: Date.now().toString() + Math.random(),
                      name: file.name + " (Copy)",
                      folder: selectedDestination,
                      modified: new Date().toISOString(),
                    }));
                    setFiles([...files, ...copiedFiles]);
                    setSelectedFiles(new Set());
                    setShowCopyModal(false);
                  }}
                >
                  Copy Files
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Context Menu Component */}
      <FileContextMenu
        files={files}
        selectedFiles={selectedFiles}
        onStarToggle={handleStarToggle}
        onMove={() => setShowMoveModal(true)}
        onCopy={() => setShowCopyModal(true)}
        onDelete={() => setShowDeleteModal(true)}
      />
    </div>
  );
}

// Context Menu Component
function FileContextMenu({
  files,
  selectedFiles,
  onStarToggle,
  onMove,
  onCopy,
  onDelete,
}) {
  const [showMenu, setShowMenu] = useState(false);
  const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 });
  const [targetFile, setTargetFile] = useState(null);

  useEffect(() => {
    const handleContextMenu = (e) => {
      const fileElement = e.target.closest("[data-file-id]");
      if (fileElement) {
        e.preventDefault();
        const fileId = fileElement.getAttribute("data-file-id");
        const file = files.find((f) => f.id === fileId);

        setTargetFile(file);
        setMenuPosition({ x: e.clientX, y: e.clientY });
        setShowMenu(true);
      }
    };

    const handleClick = () => {
      setShowMenu(false);
    };

    document.addEventListener("contextmenu", handleContextMenu);
    document.addEventListener("click", handleClick);

    return () => {
      document.removeEventListener("contextmenu", handleContextMenu);
      document.removeEventListener("click", handleClick);
    };
  }, [files]);

  if (!showMenu || !targetFile) return null;

  const menuItems = [
    { icon: Eye, label: "View", action: () => console.log("View file") },
    {
      icon: Download,
      label: "Download",
      action: () => console.log("Download file"),
    },
    { icon: Share2, label: "Share", action: () => console.log("Share file") },
    { separator: true },
    {
      icon: Star,
      label: targetFile.starred ? "Remove Star" : "Star",
      action: () => onStarToggle(targetFile.id),
    },
    { icon: Edit3, label: "Rename", action: () => console.log("Rename file") },
    { separator: true },
    { icon: Copy, label: "Copy", action: onCopy },
    { icon: Move, label: "Move", action: onMove },
    { separator: true },
    {
      icon: Trash2,
      label: "Delete",
      action: onDelete,
      className: "text-red-600 hover:bg-red-50",
    },
  ];

  return (
    <div
      className="fixed bg-white border border-slate-200 rounded-lg shadow-lg py-2 z-50 min-w-[160px]"
      style={{
        left: menuPosition.x,
        top: menuPosition.y,
        transform: "translateY(-10px)",
      }}
    >
      {menuItems.map((item, index) => {
        if (item.separator) {
          return <div key={index} className="border-t border-slate-200 my-1" />;
        }

        const Icon = item.icon;
        return (
          <button
            key={index}
            onClick={(e) => {
              e.stopPropagation();
              item.action();
              setShowMenu(false);
            }}
            className={`w-full flex items-center px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors ${
              item.className || ""
            }`}
          >
            <Icon className="w-4 h-4 mr-3" />
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

// File Upload Component (drag & drop)
function FileUploadZone({ onFileUpload, className = "" }) {
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      for (let i = 0; i < e.dataTransfer.files.length; i++) {
        onFileUpload(e.dataTransfer.files[i]);
      }
    }
  };

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-8 text-center transition-all ${
        dragActive
          ? "border-blue-500 bg-blue-50"
          : "border-slate-300 hover:border-slate-400"
      } ${className}`}
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
    >
      <Upload
        className={`w-12 h-12 mx-auto mb-4 ${
          dragActive ? "text-blue-500" : "text-slate-400"
        }`}
      />
      <h3 className="text-lg font-medium text-slate-900 mb-2">
        {dragActive ? "Drop files here" : "Drag & drop files here"}
      </h3>
      <p className="text-slate-500 mb-4">or click to browse your files</p>
      <Button className="bg-blue-600 hover:bg-blue-700">Choose Files</Button>
    </div>
  );
}
