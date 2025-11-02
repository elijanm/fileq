// components/FileManager/utils/fileUtils.js
import {
  Folder,
  FileText,
  Image,
  Video,
  Headphones,
  Archive,
  File,
  Layers,
  BarChart3,
  Code,
} from "lucide-react";

// File type icons and colors
export const getFileIcon = (type) => {
  const icons = {
    folder: { icon: Folder, color: "#3b82f6", bg: "#dbeafe" },
    pdf: { icon: FileText, color: "#dc2626", bg: "#fecaca" },
    image: { icon: Image, color: "#059669", bg: "#a7f3d0" },
    video: { icon: Video, color: "#d97706", bg: "#fed7aa" },
    audio: { icon: Headphones, color: "#7c3aed", bg: "#ddd6fe" },
    archive: { icon: Archive, color: "#6366f1", bg: "#e0e7ff" },
    document: { icon: File, color: "#0891b2", bg: "#a5f3fc" },
    presentation: { icon: Layers, color: "#ea580c", bg: "#fed7aa" },
    spreadsheet: { icon: BarChart3, color: "#16a34a", bg: "#bbf7d0" },
    code: { icon: Code, color: "#8b5cf6", bg: "#ede9fe" },
    text: { icon: FileText, color: "#6b7280", bg: "#f3f4f6" },
    default: { icon: File, color: "#6b7280", bg: "#f3f4f6" },
  };
  return icons[type] || icons.default;
};

// Format file size
export const formatFileSize = (bytes) => {
  if (bytes === 0 || isNaN(bytes)) return "0 KB";
  const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + " " + sizes[i];
};

// Format date
export const formatDate = (dateString) => {
  const date = new Date(dateString);
  const now = new Date();
  const diffTime = Math.abs(now - date);
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 1) return "Today";
  if (diffDays === 2) return "Yesterday";
  if (diffDays <= 7) return `${diffDays} days ago`;
  if (diffDays <= 30) return `${Math.ceil(diffDays / 7)} weeks ago`;
  if (diffDays <= 365) return `${Math.ceil(diffDays / 30)} months ago`;
  return date.toLocaleDateString();
};

// Get file type from name and MIME type
export const getFileType = (fileName, mimeType) => {
  const extension = fileName.split(".").pop()?.toLowerCase();

  if (mimeType?.startsWith("image/")) return "image";
  if (mimeType?.startsWith("video/")) return "video";
  if (mimeType?.startsWith("audio/")) return "audio";
  if (mimeType?.includes("pdf")) return "pdf";

  switch (extension) {
    case "pdf":
      return "pdf";
    case "doc":
    case "docx":
    case "txt":
    case "rtf":
      return "document";
    case "xls":
    case "xlsx":
    case "csv":
      return "spreadsheet";
    case "ppt":
    case "pptx":
      return "presentation";
    case "zip":
    case "rar":
    case "7z":
    case "tar":
    case "gz":
      return "archive";
    case "mp3":
    case "wav":
    case "flac":
    case "aac":
    case "m4a":
      return "audio";
    case "mp4":
    case "avi":
    case "mkv":
    case "mov":
    case "wmv":
    case "flv":
      return "video";
    case "jpg":
    case "jpeg":
    case "png":
    case "gif":
    case "svg":
    case "webp":
    case "bmp":
      return "image";
    case "js":
    case "jsx":
    case "ts":
    case "tsx":
    case "html":
    case "css":
    case "py":
    case "java":
    case "cpp":
    case "c":
    case "php":
      return "code";
    case "txt":
    case "md":
    case "markdown":
      return "text";
    default:
      return "document";
  }
};

// Generate file thumbnail URL
export const getFileThumbnail = (file) => {
  if (file.thumbnail) return file.thumbnail;

  // Generate placeholder thumbnails based on file type
  const type = file.type;
  const colors = {
    pdf: "#dc2626",
    image: "#059669",
    video: "#d97706",
    audio: "#7c3aed",
    document: "#0891b2",
    presentation: "#ea580c",
    spreadsheet: "#16a34a",
    code: "#8b5cf6",
    text: "#6b7280",
  };

  return `data:image/svg+xml,${encodeURIComponent(`
    <svg width="120" height="120" xmlns="http://www.w3.org/2000/svg">
      <rect width="120" height="120" fill="${
        colors[type] || "#6b7280"
      }" opacity="0.1"/>
      <text x="60" y="65" font-family="Arial" font-size="12" fill="${
        colors[type] || "#6b7280"
      }" text-anchor="middle">${
    file.name.split(".").pop()?.toUpperCase() || "FILE"
  }</text>
    </svg>
  `)}`;
};

// Validate file name
export const validateFileName = (name) => {
  const invalidChars = /[<>:"/\\|?*\x00-\x1f]/;
  const reservedNames = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i;

  if (!name || name.trim() === "") {
    return { valid: false, error: "File name cannot be empty" };
  }

  if (name.length > 255) {
    return { valid: false, error: "File name too long (max 255 characters)" };
  }

  if (invalidChars.test(name)) {
    return { valid: false, error: "File name contains invalid characters" };
  }

  if (reservedNames.test(name)) {
    return { valid: false, error: "File name is reserved by the system" };
  }

  return { valid: true };
};

// Check if file is supported for preview
export const isPreviewSupported = (file) => {
  const previewableTypes = ["image", "pdf", "text", "code"];
  return previewableTypes.includes(file.type);
};

// Generate share URL
export const generateShareUrl = (fileId, options = {}) => {
  const baseUrl = "https://filemanager.app/share";
  const params = new URLSearchParams();

  if (options.password) params.append("p", "1");
  if (options.expiresAt) params.append("exp", options.expiresAt);
  if (options.downloadOnly) params.append("dl", "1");

  const queryString = params.toString();
  return `${baseUrl}/${fileId}${queryString ? `?${queryString}` : ""}`;
};

// Calculate folder statistics
export const calculateFolderStats = (files, folderPath) => {
  const folderFiles = files.filter((file) => file.folder === folderPath);

  const stats = {
    totalItems: folderFiles.length,
    totalSize: 0,
    folders: 0,
    files: 0,
    typeBreakdown: {},
    lastModified: null,
    oldestFile: null,
  };

  let latestDate = new Date(0);
  let oldestDate = new Date();

  folderFiles.forEach((file) => {
    const fileDate = new Date(file.modified);

    if (file.type === "folder") {
      stats.folders++;
    } else {
      stats.files++;
      stats.totalSize += file.sizeBytes || 0;
    }

    // Type breakdown
    stats.typeBreakdown[file.type] = (stats.typeBreakdown[file.type] || 0) + 1;

    // Date tracking
    if (fileDate > latestDate) {
      latestDate = fileDate;
      stats.lastModified = file;
    }

    if (fileDate < oldestDate) {
      oldestDate = fileDate;
      stats.oldestFile = file;
    }
  });

  return stats;
};
