// components/FileManager/components/MoveFilesModal.jsx
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  X,
  Move,
  Folder,
  ChevronRight,
  ChevronDown,
  FolderPlus,
  Home,
  Search,
  ArrowLeft,
} from "lucide-react";
import { getFileIcon } from "@/components/filemanager/utils/fileUtils";

export default function MoveFilesModal({
  isOpen,
  onClose,
  onMove,
  selectedFiles,
  folders,
  files,
}) {
  const [selectedDestination, setSelectedDestination] = useState("/");
  const [expandedFolders, setExpandedFolders] = useState(new Set(["root"]));
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [isMoving, setIsMoving] = useState(false);

  if (!isOpen) return null;

  // Get selected files data
  const selectedFilesData = files.filter((file) => selectedFiles.has(file.id));

  // Build folder tree structure
  const buildFolderTree = () => {
    const tree = {};

    // Add root folder
    tree["/"] = {
      id: "root",
      name: "Home",
      path: "/",
      parent: null,
      children: [],
    };

    // Process all folders
    folders.forEach((folder) => {
      if (folder.id !== "root") {
        tree[folder.path] = {
          ...folder,
          children: [],
        };
      }
    });

    // Add folders found in files data
    const folderPaths = new Set();
    files.forEach((file) => {
      if (file.type === "folder") {
        folderPaths.add(
          file.folder + (file.folder === "/" ? "" : "/") + file.name
        );
      }
    });

    folderPaths.forEach((path) => {
      if (!tree[path]) {
        const parts = path.split("/").filter(Boolean);
        const name = parts[parts.length - 1];
        tree[path] = {
          id: path.replace(/[^a-zA-Z0-9]/g, "_"),
          name: name,
          path: path,
          parent: parts.length > 1 ? "/" + parts.slice(0, -1).join("/") : "/",
          children: [],
        };
      }
    });

    // Build parent-child relationships
    Object.values(tree).forEach((folder) => {
      if (folder.parent && tree[folder.parent]) {
        tree[folder.parent].children.push(folder);
      }
    });

    return tree;
  };

  const folderTree = buildFolderTree();

  const toggleFolderExpansion = (folderId) => {
    const newExpanded = new Set(expandedFolders);
    if (newExpanded.has(folderId)) {
      newExpanded.delete(folderId);
    } else {
      newExpanded.add(folderId);
    }
    setExpandedFolders(newExpanded);
  };

  const handleCreateFolder = () => {
    if (!newFolderName.trim()) return;

    // Here you would typically call an API to create the folder
    console.log("Creating folder:", newFolderName, "in:", selectedDestination);

    setNewFolderName("");
    setShowCreateFolder(false);
  };

  const handleMove = async () => {
    setIsMoving(true);
    try {
      await onMove(selectedDestination);
      onClose();
    } catch (error) {
      console.error("Error moving files:", error);
    } finally {
      setIsMoving(false);
    }
  };

  const canMoveToDestination = (destination) => {
    // Check if any selected files are folders that would create a circular reference
    return !selectedFilesData.some((file) => {
      if (file.type === "folder") {
        // Can't move a folder into itself or its children
        return (
          destination.startsWith(file.folder + "/" + file.name) ||
          destination === file.folder + "/" + file.name
        );
      }
      return false;
    });
  };

  const FolderTreeNode = ({ folder, level = 0 }) => {
    const isExpanded = expandedFolders.has(folder.id);
    const isSelected = selectedDestination === folder.path;
    const hasChildren = folder.children && folder.children.length > 0;
    const canMoveTo = canMoveToDestination(folder.path);

    // Filter children based on search
    const filteredChildren =
      folder.children?.filter((child) =>
        child.name.toLowerCase().includes(searchQuery.toLowerCase())
      ) || [];

    return (
      <div className="select-none">
        <div
          className={`flex items-center py-2 px-2 rounded-lg cursor-pointer transition-colors ${
            isSelected
              ? "bg-blue-100 text-blue-700"
              : canMoveTo
              ? "hover:bg-gray-50"
              : "opacity-50 cursor-not-allowed"
          }`}
          style={{ marginLeft: `${level * 20}px` }}
          onClick={() => canMoveTo && setSelectedDestination(folder.path)}
        >
          <div className="flex items-center flex-1 min-w-0">
            {hasChildren && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  toggleFolderExpansion(folder.id);
                }}
                className="mr-1 p-1 hover:bg-gray-200 rounded"
              >
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
              </button>
            )}

            {!hasChildren && <div className="w-6" />}

            <Folder className="w-4 h-4 mr-2 text-blue-600" />
            <span className="truncate">{folder.name}</span>
          </div>

          {isSelected && <div className="w-2 h-2 bg-blue-600 rounded-full" />}
        </div>

        {isExpanded && hasChildren && (
          <div>
            {filteredChildren.map((child) => (
              <FolderTreeNode key={child.id} folder={child} level={level + 1} />
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl max-h-[80vh] flex flex-col">
        <CardHeader className="border-b flex-shrink-0">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center">
              <Move className="w-5 h-5 mr-2 text-blue-600" />
              Move {selectedFiles.size}{" "}
              {selectedFiles.size === 1 ? "Item" : "Items"}
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="w-4 h-4" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-6 flex-1 overflow-hidden flex flex-col">
          {/* Selected Files Preview */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Moving:</h3>
            <div className="bg-gray-50 rounded-lg p-3 max-h-32 overflow-y-auto">
              {selectedFilesData.slice(0, 5).map((file) => {
                const { icon: Icon, color } = getFileIcon(file.type);
                return (
                  <div
                    key={file.id}
                    className="flex items-center space-x-2 py-1"
                  >
                    <Icon className="w-4 h-4" style={{ color }} />
                    <span className="text-sm text-gray-700 truncate">
                      {file.name}
                    </span>
                  </div>
                );
              })}
              {selectedFilesData.length > 5 && (
                <div className="text-sm text-gray-500 py-1">
                  +{selectedFilesData.length - 5} more files...
                </div>
              )}
            </div>
          </div>

          {/* Search */}
          <div className="mb-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search folders..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Destination Selection */}
          <div className="flex-1 overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-700">
                Choose Destination:
              </h3>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowCreateFolder(true)}
              >
                <FolderPlus className="w-4 h-4 mr-2" />
                New Folder
              </Button>
            </div>

            <div className="flex-1 border border-gray-200 rounded-lg p-3 overflow-y-auto bg-white">
              <FolderTreeNode folder={folderTree["/"]} />
            </div>
          </div>

          {/* Current Selection Display */}
          <div className="mt-4 p-3 bg-blue-50 rounded-lg">
            <div className="flex items-center text-sm">
              <Home className="w-4 h-4 mr-2 text-blue-600" />
              <span className="text-blue-700 font-medium">Destination: </span>
              <span className="text-blue-600 ml-1">
                {selectedDestination === "/" ? "Home" : selectedDestination}
              </span>
            </div>
            {!canMoveToDestination(selectedDestination) && (
              <div className="text-red-600 text-sm mt-2">
                Cannot move folder into itself or its children
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end space-x-3 mt-6">
            <Button variant="outline" onClick={onClose} disabled={isMoving}>
              Cancel
            </Button>
            <Button
              onClick={handleMove}
              disabled={
                isMoving ||
                !canMoveToDestination(selectedDestination) ||
                selectedDestination === "/"
              }
              className="bg-blue-600 hover:bg-blue-700"
            >
              {isMoving ? (
                <div className="flex items-center">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Moving...
                </div>
              ) : (
                <>
                  <Move className="w-4 h-4 mr-2" />
                  Move {selectedFiles.size}{" "}
                  {selectedFiles.size === 1 ? "Item" : "Items"}
                </>
              )}
            </Button>
          </div>
        </CardContent>

        {/* Create Folder Modal */}
        {showCreateFolder && (
          <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
            <Card className="w-full max-w-sm mx-4">
              <CardHeader>
                <CardTitle className="text-base">Create New Folder</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Folder Name
                  </label>
                  <input
                    type="text"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    placeholder="Enter folder name"
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                    Create
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </Card>
    </div>
  );
}
