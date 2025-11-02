// components/FileManager/components/FileList.jsx
import React, { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import clsx from "clsx";
import SelectAllCheckbox from "@/components/SelectAllCheckbox";
import {
  Star,
  Share2,
  MoreVertical,
  Download,
  FolderOpen,
  ChevronDown,
  ChevronUp,
  Eye,
  Edit3,
  Calendar,
  User,
  HardDrive,
} from "lucide-react";
import {
  getFileIcon,
  formatDate,
  formatFileSize,
} from "@/components/filemanager/utils/fileUtils";

export default function FileList({
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
  const [sortConfig, setSortConfig] = useState({
    field: null,
    direction: null,
  });
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

  const handleSelectAll = () => {
    if (selectedFiles.size === files.length && files.length > 0) {
      // Deselect all
      files.forEach((file) => onFileSelect(file.id));
    } else {
      // Select all
      files.forEach((file) => {
        if (!selectedFiles.has(file.id)) {
          onFileSelect(file.id);
        }
      });
    }
  };

  const handleSort = (field) => {
    let direction = "asc";
    if (sortConfig.field === field && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ field, direction });
  };

  const getSortedFiles = () => {
    if (!sortConfig.field) return files;

    return [...files].sort((a, b) => {
      let aValue = a[sortConfig.field];
      let bValue = b[sortConfig.field];

      // Sort folders first
      if (a.type === "folder" && b.type !== "folder") return -1;
      if (a.type !== "folder" && b.type === "folder") return 1;

      // Handle different data types
      if (sortConfig.field === "size") {
        aValue = a.sizeBytes || 0;
        bValue = b.sizeBytes || 0;
      } else if (sortConfig.field === "modified") {
        aValue = new Date(a.modified);
        bValue = new Date(b.modified);
      } else if (typeof aValue === "string") {
        aValue = aValue.toLowerCase();
        bValue = bValue.toLowerCase();
      }

      if (aValue < bValue) return sortConfig.direction === "asc" ? -1 : 1;
      if (aValue > bValue) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
  };

  const SortIcon = ({ field }) => {
    if (sortConfig.field !== field) return null;
    return sortConfig.direction === "asc" ? (
      <ChevronUp className="w-4 h-4 inline ml-1" />
    ) : (
      <ChevronDown className="w-4 h-4 inline ml-1" />
    );
  };

  // In FileList.jsx - update the FileRow component
  const FileRow_ = ({ file }) => {
    const { icon: Icon, color } = getFileIcon(file.type);
    const isSelected = selectedFiles.has(file.id);

    return (
      <tr
        className={`hover:bg-slate-50 cursor-pointer transition-colors group ${
          isSelected ? "bg-blue-50 border-l-4 border-l-blue-500" : ""
        } ${
          dragTarget === file.id
            ? "bg-green-50 border-l-4 border-l-green-500"
            : ""
        }`}
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
        {/* rest of your row content */}
      </tr>
    );
  };

  const FileRow = ({ file }) => {
    const { icon: Icon, color } = getFileIcon(file.type);
    const isSelected = selectedFiles.has(file.id);

    return (
      <tr
        // className={clsx(
        //   "hover:bg-slate-50 cursor-pointer transition-colors group",
        //   isSelected && "bg-blue-50 border-l-4 border-l-blue-500",
        //   dragTarget === file.id && "bg-green-50 border-l-4 border-l-green-500"
        // )}
        className={`hover:bg-slate-50 cursor-pointer transition-colors group ${
          isSelected ? "bg-blue-50 border-l-4 border-l-blue-500" : ""
        } ${
          dragTarget === file.id
            ? "bg-green-50 border-l-4 border-l-green-500"
            : ""
        }`}
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
        {/* Selection & Name Column */}
        <td className="px-6 py-4 w-1/2">
          <div className="flex items-center space-x-3">
            <SelectAllCheckbox
              files={files}
              selectedFiles={selectedFiles}
              onChange={handleSelectAll}
            />
            {/* <input
              type="checkbox"
              checked={isSelected}
              onChange={(e) => {
                e.stopPropagation();
                onFileSelect(file.id);
              }}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              onClick={(e) => e.stopPropagation()}
            /> */}

            <div className="flex items-center space-x-3 flex-1 min-w-0">
              <div className="relative flex-shrink-0">
                <Icon className="w-5 h-5" style={{ color }} />
                {file.type === "folder" && (
                  <div className="absolute -top-1 -right-1 bg-white rounded-full p-0.5 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity">
                    <FolderOpen className="w-3 h-3 text-blue-500" />
                  </div>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2">
                  <p className="font-medium text-slate-900 truncate">
                    {file.name}
                  </p>

                  {/* Status badges */}
                  <div className="flex items-center space-x-1">
                    {file.starred && (
                      <Star className="w-4 h-4 text-yellow-500 fill-current flex-shrink-0" />
                    )}
                    {file.shared && (
                      <Share2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                    )}
                  </div>
                </div>

                {/* File description or type info */}
                {file.description && (
                  <p className="text-sm text-slate-500 truncate mt-1">
                    {file.description}
                  </p>
                )}

                {/* Tags */}
                {file.tags && file.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
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
            </div>
          </div>
        </td>

        {/* Size Column */}
        <td className="px-6 py-4 text-sm text-slate-500 w-24">
          {file.type === "folder" ? (
            <span className="flex items-center">
              <HardDrive className="w-4 h-4 mr-1" />
              {file.itemCount || 0} items
            </span>
          ) : (
            formatFileSize(file.sizeBytes)
          )}
        </td>

        {/* Modified Column */}
        <td className="px-6 py-4 text-sm text-slate-500 w-32">
          <div className="flex items-center">
            <Calendar className="w-4 h-4 mr-1" />
            {formatDate(file.modified)}
          </div>
        </td>

        {/* Owner Column */}
        <td className="px-6 py-4 text-sm text-slate-500 w-32">
          <div className="flex items-center">
            <User className="w-4 h-4 mr-1" />
            <span className="truncate">{file.owner}</span>
          </div>
        </td>

        {/* Downloads Column */}
        <td className="px-6 py-4 text-sm text-slate-500 w-24 text-center">
          {file.type !== "folder" ? (
            <span className="flex items-center justify-center">
              <Download className="w-4 h-4 mr-1" />
              {file.downloads}
            </span>
          ) : (
            "—"
          )}
        </td>

        {/* Actions Column */}
        <td className="px-6 py-4 w-20">
          <div className="flex items-center justify-center space-x-2">
            {/* Star toggle */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onStarToggle(file.id);
              }}
              className={`p-1 rounded hover:bg-slate-100 transition-colors ${
                file.starred
                  ? "opacity-100"
                  : "opacity-0 group-hover:opacity-100"
              }`}
            >
              <Star
                className={`w-4 h-4 ${
                  file.starred
                    ? "text-yellow-500 fill-current"
                    : "text-slate-400"
                }`}
              />
            </button>

            {/* Quick action button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSelectedItem(file);
                setShowRightPanel(true);
                setPanelType("details");
              }}
              className="p-1 rounded hover:bg-slate-100 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <Eye className="w-4 h-4 text-slate-500" />
            </button>

            {/* More options */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onContextMenu(e, file);
              }}
              className="p-1 rounded hover:bg-slate-100 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <MoreVertical className="w-4 h-4 text-slate-500" />
            </button>
          </div>
        </td>
      </tr>
    );
  };

  const sortedFiles = getSortedFiles();

  return (
    <Card className="border-0 shadow-sm overflow-hidden">
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            {/* Table Header */}
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                {/* Name column header */}
                <th className="px-6 py-3 text-left">
                  <div className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={
                        selectedFiles.size === files.length && files.length > 0
                      }
                      indeterminate={
                        selectedFiles.size > 0 &&
                        selectedFiles.size < files.length
                      }
                      onChange={handleSelectAll}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    <button
                      onClick={() => handleSort("name")}
                      className="flex items-center text-xs font-medium text-slate-500 uppercase tracking-wider hover:text-slate-700 transition-colors"
                    >
                      Name
                      <SortIcon field="name" />
                    </button>
                  </div>
                </th>

                {/* Size column header */}
                <th className="px-6 py-3 text-left">
                  <button
                    onClick={() => handleSort("size")}
                    className="flex items-center text-xs font-medium text-slate-500 uppercase tracking-wider hover:text-slate-700 transition-colors"
                  >
                    Size
                    <SortIcon field="size" />
                  </button>
                </th>

                {/* Modified column header */}
                <th className="px-6 py-3 text-left">
                  <button
                    onClick={() => handleSort("modified")}
                    className="flex items-center text-xs font-medium text-slate-500 uppercase tracking-wider hover:text-slate-700 transition-colors"
                  >
                    Modified
                    <SortIcon field="modified" />
                  </button>
                </th>

                {/* Owner column header */}
                <th className="px-6 py-3 text-left">
                  <button
                    onClick={() => handleSort("owner")}
                    className="flex items-center text-xs font-medium text-slate-500 uppercase tracking-wider hover:text-slate-700 transition-colors"
                  >
                    Owner
                    <SortIcon field="owner" />
                  </button>
                </th>

                {/* Downloads column header */}
                <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Downloads
                </th>

                {/* Actions column header */}
                <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>

            {/* Table Body */}
            <tbody className="bg-white divide-y divide-slate-200">
              {sortedFiles.map((file) => (
                <FileRow key={file.id} file={file} />
              ))}
            </tbody>
          </table>
        </div>

        {/* Empty state */}
        {files.length === 0 && (
          <div className="text-center py-12">
            <div className="text-slate-400 mb-4">
              <svg
                className="w-12 h-12 mx-auto"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-slate-900 mb-2">
              No files in this folder
            </h3>
            <p className="text-slate-500">
              Upload some files or create folders to get started.
            </p>
          </div>
        )}

        {/* Loading state for processing files */}
        {sortedFiles.some((file) => file.processing) && (
          <div className="border-t border-slate-200 bg-blue-50 px-6 py-3">
            <div className="flex items-center space-x-2 text-sm text-blue-700">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              <span>
                Processing {sortedFiles.filter((f) => f.processing).length}{" "}
                files...
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
