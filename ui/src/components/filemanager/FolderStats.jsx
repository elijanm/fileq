// components/FileManager/components/FolderStats.jsx
import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  BarChart3,
  Files,
  HardDrive,
  Clock,
  TrendingUp,
  Users,
  FileType,
  Calendar,
  Activity,
  Folder,
  PieChart,
} from "lucide-react";
import {
  formatFileSize,
  formatDate,
  getFileIcon,
} from "@/components/filemanager/utils/fileUtils";

export default function FolderStats({ folder, files, currentFolder }) {
  // Calculate folder statistics
  const folderFiles = files.filter(
    (file) =>
      file.folder === currentFolder ||
      (folder.name &&
        file.folder ===
          `${currentFolder === "/" ? "" : currentFolder}/${folder.name}`)
  );

  const stats = {
    totalItems: folderFiles.length,
    totalSize: 0,
    folders: 0,
    files: 0,
    typeBreakdown: {},
    lastModified: null,
    owners: new Set(),
    sharedFiles: 0,
    starredFiles: 0,
  };

  let latestDate = new Date(0);

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

    // Other stats
    stats.owners.add(file.owner);
    if (file.shared) stats.sharedFiles++;
    if (file.starred) stats.starredFiles++;

    // Latest modification
    if (fileDate > latestDate) {
      latestDate = fileDate;
      stats.lastModified = file;
    }
  });

  // Most common file types
  const sortedTypes = Object.entries(stats.typeBreakdown)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  // Calculate percentages for type breakdown
  const totalFiles = stats.files + stats.folders;

  return (
    <div className="space-y-6">
      <div className="text-center">
        <Folder className="w-12 h-12 mx-auto text-blue-600 mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Folder Statistics
        </h3>
        <p className="text-sm text-gray-600">
          Overview of contents and activity
        </p>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <Files className="w-6 h-6 mx-auto text-blue-600 mb-2" />
            <div className="text-2xl font-bold text-gray-900">
              {stats.totalItems}
            </div>
            <div className="text-sm text-gray-500">Total Items</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <HardDrive className="w-6 h-6 mx-auto text-green-600 mb-2" />
            <div className="text-2xl font-bold text-gray-900">
              {formatFileSize(stats.totalSize)}
            </div>
            <div className="text-sm text-gray-500">Total Size</div>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Statistics */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center">
            <BarChart3 className="w-4 h-4 mr-2" />
            Content Breakdown
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600 flex items-center">
              <Folder className="w-4 h-4 mr-2" />
              Folders
            </span>
            <span className="text-sm font-medium">
              {stats.folders} (
              {totalFiles > 0
                ? Math.round((stats.folders / totalFiles) * 100)
                : 0}
              %)
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600 flex items-center">
              <FileType className="w-4 h-4 mr-2" />
              Files
            </span>
            <span className="text-sm font-medium">
              {stats.files} (
              {totalFiles > 0
                ? Math.round((stats.files / totalFiles) * 100)
                : 0}
              %)
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600 flex items-center">
              <Users className="w-4 h-4 mr-2" />
              Contributors
            </span>
            <span className="text-sm font-medium">{stats.owners.size}</span>
          </div>
        </CardContent>
      </Card>

      {/* File Types Distribution */}
      {sortedTypes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center">
              <PieChart className="w-4 h-4 mr-2" />
              File Types
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {sortedTypes.map(([type, count]) => {
              const { icon: Icon, color } = getFileIcon(type);
              const percentage =
                totalFiles > 0 ? Math.round((count / totalFiles) * 100) : 0;

              return (
                <div key={type} className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Icon className="w-4 h-4" style={{ color }} />
                    <span className="text-sm text-gray-600 capitalize">
                      {type}s
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{
                          width: `${percentage}%`,
                          backgroundColor: color,
                        }}
                      ></div>
                    </div>
                    <span className="text-sm font-medium w-8 text-right">
                      {count}
                    </span>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Activity Information */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center">
            <Activity className="w-4 h-4 mr-2" />
            Activity
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {stats.lastModified && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-600 flex items-center">
                  <Clock className="w-4 h-4 mr-2" />
                  Last Modified
                </span>
              </div>
              <div className="bg-gray-50 p-3 rounded-lg">
                <div className="font-medium text-sm">
                  {stats.lastModified.name}
                </div>
                <div className="text-xs text-gray-500">
                  {formatDate(stats.lastModified.modified)} by{" "}
                  {stats.lastModified.owner}
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            {stats.sharedFiles > 0 && (
              <div className="text-center">
                <div className="text-lg font-semibold text-green-600">
                  {stats.sharedFiles}
                </div>
                <div className="text-xs text-gray-500">Shared Files</div>
              </div>
            )}

            {stats.starredFiles > 0 && (
              <div className="text-center">
                <div className="text-lg font-semibold text-yellow-600">
                  {stats.starredFiles}
                </div>
                <div className="text-xs text-gray-500">Starred Files</div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Storage Usage Visualization */}
      {stats.totalSize > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center">
              <TrendingUp className="w-4 h-4 mr-2" />
              Storage Usage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {sortedTypes
                .filter(([type]) => type !== "folder")
                .map(([type, count]) => {
                  const typeFiles = folderFiles.filter(
                    (f) => f.type === type && f.type !== "folder"
                  );
                  const typeSize = typeFiles.reduce(
                    (sum, f) => sum + (f.sizeBytes || 0),
                    0
                  );
                  const percentage =
                    stats.totalSize > 0
                      ? (typeSize / stats.totalSize) * 100
                      : 0;
                  const { icon: Icon, color } = getFileIcon(type);

                  if (typeSize === 0) return null;

                  return (
                    <div
                      key={type}
                      className="flex items-center justify-between"
                    >
                      <div className="flex items-center space-x-2">
                        <Icon className="w-4 h-4" style={{ color }} />
                        <span className="text-sm text-gray-600 capitalize">
                          {type}s
                        </span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-300"
                            style={{
                              width: `${Math.max(percentage, 2)}%`,
                              backgroundColor: color,
                            }}
                          ></div>
                        </div>
                        <span className="text-sm font-medium w-12 text-right">
                          {formatFileSize(typeSize)}
                        </span>
                      </div>
                    </div>
                  );
                })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Activity Timeline */}
      {folderFiles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center">
              <Calendar className="w-4 h-4 mr-2" />
              Recent Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {folderFiles
                .sort((a, b) => new Date(b.modified) - new Date(a.modified))
                .slice(0, 5)
                .map((file) => {
                  const { icon: Icon, color } = getFileIcon(file.type);
                  return (
                    <div
                      key={file.id}
                      className="flex items-center space-x-3 p-2 hover:bg-gray-50 rounded"
                    >
                      <div className="flex-shrink-0">
                        <Icon className="w-4 h-4" style={{ color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 truncate">
                          {file.name}
                        </div>
                        <div className="text-xs text-gray-500">
                          Modified {formatDate(file.modified)}
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
