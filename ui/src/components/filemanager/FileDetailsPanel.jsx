// components/FileManager/components/FileDetailsPanel.jsx
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  X,
  Info,
  Settings,
  User,
  Calendar,
  HardDrive,
  Star,
  Share2,
  Download,
  Tag,
  Eye,
  BarChart3,
  FileType,
  Users,
  Clock,
  Edit3,
} from "lucide-react";

// Import specialized tool components
import PDFTools from "@/components/filemanager/tools/PDFTools";
import AudioTools from "@/components/filemanager/tools/AudioTools";
// import VideoTools from "@/components/filemanager/tools/VideoTools";
import ImageTools from "@/components/filemanager/tools/ImageTools";
import TextTools from "@/components/filemanager/tools/TextTools";
import FolderStats from "@/components/filemanager/FolderStats";
import { getFileIcon } from "@/components/filemanager/utils/fileUtils";

export default function FileDetailsPanel({
  item,
  panelType,
  setPanelType,
  onClose,
  files,
  currentFolder,
}) {
  const [editingTags, setEditingTags] = useState(false);
  const [newTag, setNewTag] = useState("");

  if (!item) return null;

  const { icon: Icon, color, bg } = getFileIcon(item.type);

  const formatFileSize = (bytes) => {
    if (bytes === 0 || isNaN(bytes)) return "0 KB";
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + " " + sizes[i];
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const renderToolsPanel = () => {
    switch (item.type) {
      case "pdf":
        return <PDFTools file={item} />;
      case "audio":
        return <AudioTools file={item} />;
      //   case "video":
      //     return <VideoTools file={item} />;
      case "image":
        return <ImageTools file={item} />;
      case "document":
      case "text":
        return <TextTools file={item} />;
      case "folder":
        return (
          <FolderStats
            folder={item}
            files={files}
            currentFolder={currentFolder}
          />
        );
      default:
        return (
          <div className="text-center py-8 text-slate-500">
            <Settings className="w-12 h-12 mx-auto mb-4 text-slate-300" />
            <p>No tools available for this file type</p>
          </div>
        );
    }
  };

  return (
    <div className="fixed right-0 top-16 bottom-0 w-80 bg-white border-l border-slate-200 shadow-lg z-40 overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b border-slate-200 p-4 z-10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">
            {item.type === "folder" ? "Folder Details" : "File Details"}
          </h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Tab navigation */}
        <div className="flex space-x-1">
          <button
            onClick={() => setPanelType("details")}
            className={`flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
              panelType === "details"
                ? "bg-blue-100 text-blue-700"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            }`}
          >
            <Info className="w-4 h-4 mr-2" />
            Details
          </button>
          <button
            onClick={() => setPanelType("tools")}
            className={`flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
              panelType === "tools"
                ? "bg-blue-100 text-blue-700"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            }`}
          >
            <Settings className="w-4 h-4 mr-2" />
            {item.type === "folder" ? "Statistics" : "Tools"}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {panelType === "details" ? (
          <div className="space-y-6">
            {/* File/Folder Icon and Name */}
            <div className="text-center">
              <div
                className="inline-flex p-4 rounded-2xl mb-4"
                style={{ backgroundColor: bg }}
              >
                <Icon className="w-8 h-8" style={{ color }} />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">
                {item.name}
              </h3>
              {item.description && (
                <p className="text-sm text-slate-600">{item.description}</p>
              )}
            </div>

            {/* Quick Actions */}
            <div className="flex justify-center space-x-2">
              {item.type !== "folder" && (
                <Button size="sm" variant="outline">
                  <Download className="w-4 h-4 mr-2" />
                  Download
                </Button>
              )}
              <Button size="sm" variant="outline">
                <Share2 className="w-4 h-4 mr-2" />
                Share
              </Button>
              <Button size="sm" variant="outline">
                <Edit3 className="w-4 h-4 mr-2" />
                Rename
              </Button>
            </div>

            {/* Properties */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Properties</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-600 flex items-center">
                    <FileType className="w-4 h-4 mr-2" />
                    Type
                  </span>
                  <span className="text-sm font-medium capitalize">
                    {item.type === "folder" ? "Folder" : item.type}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-600 flex items-center">
                    <HardDrive className="w-4 h-4 mr-2" />
                    Size
                  </span>
                  <span className="text-sm font-medium">
                    {item.type === "folder"
                      ? `${item.itemCount || 0} items`
                      : formatFileSize(item.sizeBytes)}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-600 flex items-center">
                    <User className="w-4 h-4 mr-2" />
                    Owner
                  </span>
                  <span className="text-sm font-medium">{item.owner}</span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-600 flex items-center">
                    <Calendar className="w-4 h-4 mr-2" />
                    Modified
                  </span>
                  <span className="text-sm font-medium">
                    {formatDate(item.modified)}
                  </span>
                </div>

                {item.created && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600 flex items-center">
                      <Clock className="w-4 h-4 mr-2" />
                      Created
                    </span>
                    <span className="text-sm font-medium">
                      {formatDate(item.created)}
                    </span>
                  </div>
                )}

                {/* File-specific properties */}
                {item.type === "video" && item.duration && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">Duration</span>
                    <span className="text-sm font-medium">{item.duration}</span>
                  </div>
                )}

                {item.type === "audio" && item.duration && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">Duration</span>
                    <span className="text-sm font-medium">{item.duration}</span>
                  </div>
                )}

                {item.type === "presentation" && item.slides && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">Slides</span>
                    <span className="text-sm font-medium">{item.slides}</span>
                  </div>
                )}

                {item.type !== "folder" && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600 flex items-center">
                      <Download className="w-4 h-4 mr-2" />
                      Downloads
                    </span>
                    <span className="text-sm font-medium">
                      {item.downloads}
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Tags */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center justify-between">
                  <span className="flex items-center">
                    <Tag className="w-4 h-4 mr-2" />
                    Tags
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setEditingTags(!editingTags)}
                  >
                    Edit
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2 mb-3">
                  {item.tags?.map((tag, index) => (
                    <span
                      key={index}
                      className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                  {(!item.tags || item.tags.length === 0) && (
                    <span className="text-sm text-slate-500">No tags</span>
                  )}
                </div>

                {editingTags && (
                  <div className="flex space-x-2">
                    <input
                      type="text"
                      value={newTag}
                      onChange={(e) => setNewTag(e.target.value)}
                      placeholder="Add tag..."
                      className="flex-1 px-2 py-1 text-xs border rounded"
                      onKeyPress={(e) => {
                        if (e.key === "Enter" && newTag.trim()) {
                          // Add tag logic here
                          setNewTag("");
                        }
                      }}
                    />
                    <Button size="sm" variant="outline">
                      Add
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Permissions */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center">
                  <Users className="w-4 h-4 mr-2" />
                  Permissions
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {item.permissions?.map((permission, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between"
                    >
                      <span className="text-sm capitalize">{permission}</span>
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Status indicators */}
            <div className="flex items-center justify-center space-x-6 py-4 bg-slate-50 rounded-lg">
              {item.starred && (
                <div className="flex flex-col items-center">
                  <Star className="w-5 h-5 text-yellow-500 fill-current mb-1" />
                  <span className="text-xs text-slate-600">Starred</span>
                </div>
              )}
              {item.shared && (
                <div className="flex flex-col items-center">
                  <Share2 className="w-5 h-5 text-green-500 mb-1" />
                  <span className="text-xs text-slate-600">Shared</span>
                </div>
              )}
              {item.type !== "folder" && item.downloads > 0 && (
                <div className="flex flex-col items-center">
                  <Download className="w-5 h-5 text-blue-500 mb-1" />
                  <span className="text-xs text-slate-600">
                    {item.downloads} downloads
                  </span>
                </div>
              )}
            </div>
          </div>
        ) : (
          // Tools/Statistics Panel
          <div className="space-y-4">{renderToolsPanel()}</div>
        )}
      </div>
    </div>
  );
}
