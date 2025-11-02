// components/FileManager/components/FileGrid.jsx
import { React, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Star, Share2, MoreVertical, Download, FolderOpen } from "lucide-react";
import {
  getFileIcon,
  formatDate,
} from "@/components/filemanager/utils/fileUtils";

export default function FileGrid({
  files,
  selectedFiles,
  onFileSelect,
  onFolderDoubleClick,
  onContextMenu,
  onStarToggle,
  setSelectedItem,
  setShowRightPanel,
  setPanelType,
  handleDragMoveFile,
}) {
  const [dragTarget, setDragTarget] = useState(null);

  const handleMoveFileToFolder = (draggedFile, targetFolder) => {
    if (draggedFile.folder === targetFolder.folder + "/" + targetFolder.name) {
      return; // Already in target folder
    }

    // Move file to target folder
    const newPath =
      targetFolder.folder === "/"
        ? "/" + targetFolder.name
        : targetFolder.folder + "/" + targetFolder.name;

    // onMoveFiles([draggedFile.id], newPath);
    handleDragMoveFile(newPath, [draggedFile.id]);
  };
  const handleFileClick = (file, event) => {
    if (event.detail === 2) {
      // Double click
      if (file.type === "folder") {
        onFolderDoubleClick(file);
      } else {
        // Open file details panel
        setSelectedItem(file);
        setShowRightPanel(true);
        setPanelType("details");
      }
    } else {
      // Single click - select file
      onFileSelect(file.id);
    }
  };

  const FileCard = ({ file }) => {
    const { icon: Icon, color, bg } = getFileIcon(file.type);
    const isSelected = selectedFiles.has(file.id);

    return (
      <Card
        className={`group cursor-pointer transition-all duration-200 hover:shadow-lg hover:-translate-y-1 ${
          isSelected ? "ring-2 ring-blue-500 shadow-lg" : ""
        } ${dragTarget === file.id ? "ring-2 ring-green-500 bg-green-50" : ""}`}
        data-file-id={file.id}
        onClick={(e) => handleFileClick(file, e)}
        onContextMenu={(e) => {
          e.preventDefault();
          onContextMenu(e, file);
        }}
        draggable
        onDragStart={(e) => {
          e.dataTransfer.setData(
            "application/json",
            JSON.stringify({
              type: "file",
              data: file,
            })
          );
        }}
        onDragOver={(e) => {
          if (file.type === "folder") {
            e.preventDefault();
            setDragTarget(file.id);
          }
        }}
        onDragLeave={(e) => {
          setDragTarget(null);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragTarget(null);
          const draggedData = JSON.parse(
            e.dataTransfer.getData("application/json")
          );
          if (draggedData.type === "file" && draggedData.data.id !== file.id) {
            handleMoveFileToFolder(draggedData.data, file);
          }
        }}
      >
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div
              className="p-3 rounded-xl group-hover:scale-110 transition-transform relative"
              style={{ backgroundColor: bg }}
            >
              <Icon className="w-6 h-6" style={{ color }} />
              {file.type === "folder" && (
                <div className="absolute -top-1 -right-1 bg-white rounded-full p-1 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity">
                  <FolderOpen className="w-3 h-3 text-blue-500" />
                </div>
              )}
            </div>
            <div className="flex items-center space-x-1">
              {file.starred && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onStarToggle(file.id);
                  }}
                  className="opacity-100 group-hover:opacity-100 p-1 hover:bg-yellow-100 rounded"
                >
                  <Star className="w-4 h-4 text-yellow-500 fill-current" />
                </button>
              )}
              {!file.starred && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onStarToggle(file.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-slate-100 rounded"
                >
                  <Star className="w-4 h-4 text-slate-400" />
                </button>
              )}
              {file.shared && <Share2 className="w-4 h-4 text-green-500" />}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onContextMenu(e, file);
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
              <span className="truncate">{file.owner}</span>
              {file.type !== "folder" && (
                <span className="flex items-center ml-2">
                  <Download className="w-3 h-3 mr-1" />
                  {file.downloads}
                </span>
              )}
            </div>

            {/* Tags */}
            {file.tags && file.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {file.tags.slice(0, 2).map((tag, index) => (
                  <span
                    key={index}
                    className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-xs rounded"
                  >
                    {tag}
                  </span>
                ))}
                {file.tags.length > 2 && (
                  <span className="px-1.5 py-0.5 bg-slate-100 text-slate-600 text-xs rounded">
                    +{file.tags.length - 2}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Progress bar for uploads/processing */}
          {file.processing && (
            <div className="mt-3">
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div
                  className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${file.progress || 0}%` }}
                ></div>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {file.processing === "uploading"
                  ? "Uploading..."
                  : "Processing..."}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {files.map((file) => (
        <FileCard key={file.id} file={file} />
      ))}
    </div>
  );
}
