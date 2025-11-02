// components/FileManager/FileManager.jsx - Main File Manager Component
import React, { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Files,
  Search,
  Grid3X3,
  List,
  FolderPlus,
  Upload,
  ArrowLeft,
  RefreshCw,
  Filter,
} from "lucide-react";

// Import subcomponents
import FileGrid from "@/components/filemanager/FileGrid";
import FileList from "@/components/filemanager/FileList";
import FileContextMenu from "@/components/filemanager/FileContextMenu";
import FileDetailsPanel from "@/components/filemanager/FileDetailsPanel";
import CreateFolderModal from "@/components/filemanager/CreateFolderModal";
import DeleteConfirmModal from "@/components/filemanager/DeleteConfirmModal";
import MoveFilesModal from "@/components/filemanager/MoveFilesModal";
import ShareModal from "@/components/filemanager/ShareModal";
import FiltersPanel from "@/components/filemanager/FiltersPanel";
import Breadcrumb from "@/components/filemanager/Breadcrumb";
import FileUploadZone from "@/components/filemanager/FileUploadZone";
import { useFileManager } from "@/components/filemanager/hooks/useFileManager";
import { mockFiles, mockFolders } from "@/components/filemanager/data/mockData";

export default function FileManager({ user, onBack }) {
  const {
    // State
    viewMode,
    setViewMode,
    searchQuery,
    setSearchQuery,
    selectedFiles,
    currentFolder,
    setCurrentFolder,
    showFilters,
    setShowFilters,
    showRightPanel,
    setShowRightPanel,
    selectedItem,
    setSelectedItem,
    panelType,
    setPanelType,
    files,
    setFiles,
    isLoading,
    setIsLoading,

    // Modal states
    showCreateFolder,
    setShowCreateFolder,
    showDeleteModal,
    setShowDeleteModal,
    showMoveModal,
    setShowMoveModal,
    showShareModal,
    setShowShareModal,

    // Context menu
    contextMenu,
    setContextMenu,

    // Clipboard
    clipboard,
    setClipboard,

    // Filtering and sorting
    filteredFiles,
    sortBy,
    setSortBy,
    sortOrder,
    setSortOrder,
    filterType,
    setFilterType,
    filterDate,
    setFilterDate,
    filterSize,
    setFilterSize,

    // Operations
    handleFileSelect,
    handleFolderDoubleClick,
    handleCreateFolder,
    handleDeleteFiles,
    handleMoveFiles,
    handleCopyFiles,
    handleStarToggle,
    handleContextMenu,
    handleEmptySpaceContextMenu,
    handleClipboardOperation,
    updateFolderManifest,
    handleDragMoveFile,

    // Upload
    handleFileUpload,
  } = useFileManager(mockFiles, mockFolders);
  const [showUploadZone, setShowUploadZone] = useState(false);

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

              <Button
                className="bg-blue-600 hover:bg-blue-700"
                onClick={() => setShowUploadZone(!showUploadZone)}
              >
                <Upload className="w-4 h-4 mr-2" />
                {showUploadZone ? "Hide Upload" : "Upload Files"}
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main
        // In FileManager.jsx - add to main content area
        onContextMenu={(e) => {
          // Check if click is on empty space (not on a file)
          if (!e.target.closest("[data-file-id]")) {
            e.preventDefault();
            handleEmptySpaceContextMenu(e);
          }
        }}
        className={`transition-all duration-300 ${
          showRightPanel ? "mr-80" : ""
        }`}
      >
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-6">
          {/* Toolbar */}
          <div className="flex items-center justify-between mb-6">
            <Breadcrumb
              currentFolder={currentFolder}
              setCurrentFolder={setCurrentFolder}
            />

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
                      Move
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleClipboardOperation("copy")}
                    >
                      Copy
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setShowDeleteModal(true)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              )}

              {clipboard.files.length > 0 && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleClipboardOperation("paste")}
                >
                  Paste {clipboard.files.length} items
                </Button>
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

              <Button
                variant="ghost"
                onClick={() => {
                  setIsLoading(true);
                  setTimeout(() => setIsLoading(false), 1000);
                }}
              >
                <RefreshCw
                  className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`}
                />
              </Button>
            </div>
          </div>

          {/* Filters Panel */}
          {showFilters && (
            <FiltersPanel
              filterType={filterType}
              setFilterType={setFilterType}
              filterDate={filterDate}
              setFilterDate={setFilterDate}
              filterSize={filterSize}
              setFilterSize={setFilterSize}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
            />
          )}

          {/* File Upload Zone */}
          {showUploadZone && (
            <FileUploadZone
              onFileUpload={handleFileUpload}
              currentFolder={currentFolder}
            />
          )}

          {/* Files Display */}
          {viewMode === "grid" ? (
            <FileGrid
              files={filteredFiles}
              selectedFiles={selectedFiles}
              onFileSelect={handleFileSelect}
              onFolderDoubleClick={handleFolderDoubleClick}
              onContextMenu={handleContextMenu}
              onStarToggle={handleStarToggle}
              setSelectedItem={setSelectedItem}
              setShowRightPanel={setShowRightPanel}
              setPanelType={setPanelType}
              handleDragMoveFile={handleDragMoveFile}
            />
          ) : (
            <FileList
              files={filteredFiles}
              selectedFiles={selectedFiles}
              onFileSelect={handleFileSelect}
              onFolderDoubleClick={handleFolderDoubleClick}
              onContextMenu={handleContextMenu}
              onStarToggle={handleStarToggle}
              setSelectedItem={setSelectedItem}
              setShowRightPanel={setShowRightPanel}
              setPanelType={setPanelType}
              handleDragMoveFile={handleDragMoveFile}
            />
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
        </div>
      </main>

      {/* Right Panel */}
      {showRightPanel && selectedItem && (
        <FileDetailsPanel
          item={selectedItem}
          panelType={panelType}
          setPanelType={setPanelType}
          onClose={() => setShowRightPanel(false)}
          files={files}
          currentFolder={currentFolder}
        />
      )}

      {/* Modals */}
      {showCreateFolder && (
        <CreateFolderModal
          isOpen={showCreateFolder}
          onClose={() => setShowCreateFolder(false)}
          onCreateFolder={handleCreateFolder}
          currentFolder={currentFolder}
        />
      )}

      {showDeleteModal && (
        <DeleteConfirmModal
          isOpen={showDeleteModal}
          onClose={() => setShowDeleteModal(false)}
          onConfirm={handleDeleteFiles}
          selectedCount={selectedFiles.size}
        />
      )}

      {showMoveModal && (
        <MoveFilesModal
          isOpen={showMoveModal}
          onClose={() => setShowMoveModal(false)}
          onMove={handleMoveFiles}
          selectedFiles={selectedFiles}
          folders={mockFolders}
          files={files}
        />
      )}

      {showShareModal && (
        <ShareModal
          isOpen={showShareModal}
          onClose={() => setShowShareModal(false)}
          selectedItem={selectedItem}
        />
      )}

      {/* Context Menu */}
      <FileContextMenu
        contextMenu={contextMenu}
        setContextMenu={setContextMenu}
        onStarToggle={handleStarToggle}
        onCopy={() => handleClipboardOperation("copy")}
        onCut={() => handleClipboardOperation("cut")}
        onDelete={() => setShowDeleteModal(true)}
        onShare={() => setShowShareModal(true)}
        setSelectedItem={setSelectedItem}
        setShowRightPanel={setShowRightPanel}
        setPanelType={setPanelType}
        clipboard={clipboard}
        onPaste={() => handleClipboardOperation("paste")}
      />
    </div>
  );
}
