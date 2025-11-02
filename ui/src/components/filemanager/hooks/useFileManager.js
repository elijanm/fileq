// components/FileManager/hooks/useFileManager.js
import { useState, useEffect, useCallback } from "react";

export function useFileManager(initialFiles, initialFolders) {
  // View and filter states
  const [viewMode, setViewMode] = useState("grid");
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

  // Panel and modal states
  const [showRightPanel, setShowRightPanel] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [panelType, setPanelType] = useState("details");
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [showMoveModal, setShowMoveModal] = useState(false);
  const [showCopyModal, setShowCopyModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);

  // Context menu state
  const [contextMenu, setContextMenu] = useState({
    show: false,
    x: 0,
    y: 0,
    targetFile: null,
  });

  // Clipboard state
  const [clipboard, setClipboard] = useState({
    files: [],
    operation: null, // 'copy' or 'cut'
  });

  // File data
  const [files, setFiles] = useState(initialFiles);
  const [folders, setFolders] = useState(initialFolders);
  const [folderManifest, setFolderManifest] = useState({});

  // Update folder manifest when files change
  useEffect(() => {
    updateFolderManifest();
  }, [files, currentFolder]);

  const updateFolderManifest = useCallback(() => {
    const manifest = {};

    // Group files by folder
    const folderContents = files.reduce((acc, file) => {
      if (!acc[file.folder]) {
        acc[file.folder] = [];
      }
      acc[file.folder].push(file);
      return acc;
    }, {});

    // Calculate folder statistics
    Object.keys(folderContents).forEach((folderPath) => {
      const contents = folderContents[folderPath];
      const totalSize = contents.reduce((sum, file) => sum + file.sizeBytes, 0);
      const fileTypes = [...new Set(contents.map((file) => file.type))];

      manifest[folderPath] = {
        path: folderPath,
        itemCount: contents.length,
        totalSize,
        fileTypes,
        lastModified: Math.max(
          ...contents.map((file) => new Date(file.modified).getTime())
        ),
        files: contents.map((file) => ({
          id: file.id,
          name: file.name,
          type: file.type,
          size: file.sizeBytes,
          modified: file.modified,
          owner: file.owner,
        })),
      };
    });

    setFolderManifest(manifest);
  }, [files]);

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
  const handleFileSelect = useCallback(
    (fileId) => {
      const newSelected = new Set(selectedFiles);
      if (newSelected.has(fileId)) {
        newSelected.delete(fileId);
      } else {
        newSelected.add(fileId);
      }
      setSelectedFiles(newSelected);
    },
    [selectedFiles]
  );

  // Folder navigation
  const handleFolderDoubleClick = useCallback((folder) => {
    if (folder.type === "folder") {
      const newPath =
        folder.folder === "/"
          ? `/${folder.name}`
          : `${folder.folder}/${folder.name}`;
      setCurrentFolder(newPath);
      setSelectedFiles(new Set());
    }
  }, []);
  const handleEmptySpaceContextMenu = useCallback(
    (event) => {
      event.preventDefault();
      setContextMenu({
        show: true,
        x: event.clientX,
        y: event.clientY,
        targetFile: null,
      });
    },
    [selectedFiles]
  );
  // Context menu handler
  const handleContextMenu = useCallback(
    (event, file) => {
      event.preventDefault();
      setContextMenu({
        show: true,
        x: event.clientX,
        y: event.clientY,
        targetFile: file,
      });

      // Select the file if not already selected
      if (!selectedFiles.has(file.id)) {
        setSelectedFiles(new Set([file.id]));
      }
    },
    [selectedFiles]
  );

  // File operations
  const handleCreateFolder = useCallback(
    (folderName) => {
      if (!folderName.trim()) return;

      const newFolder = {
        id: Date.now().toString(),
        name: folderName,
        type: "folder",
        size: "0 items",
        sizeBytes: 0,
        modified: new Date().toISOString(),
        created: new Date().toISOString(),
        owner: "You",
        folder: currentFolder,
        starred: false,
        shared: false,
        downloads: 0,
        thumbnail: null,
        description: "",
        tags: [],
        itemCount: 0,
        totalSize: 0,
        permissions: ["read", "write", "share"],
      };

      setFiles([...files, newFolder]);
    },
    [files, currentFolder]
  );

  const handleDeleteFiles = useCallback(() => {
    setFiles(files.filter((file) => !selectedFiles.has(file.id)));
    setSelectedFiles(new Set());
  }, [files, selectedFiles]);

  const handleStarToggle = useCallback(
    (fileId) => {
      setFiles(
        files.map((file) =>
          file.id === fileId ? { ...file, starred: !file.starred } : file
        )
      );
    },
    [files]
  );

  const handleMoveFiles = useCallback(
    (destinationPath) => {
      setFiles(
        files.map((file) =>
          selectedFiles.has(file.id)
            ? {
                ...file,
                folder: destinationPath,
                modified: new Date().toISOString(),
              }
            : file
        )
      );
      setSelectedFiles(new Set());
    },
    [files, selectedFiles]
  );

  const handleCopyFiles = useCallback(
    (destinationPath) => {
      const filesToCopy = files.filter((file) => selectedFiles.has(file.id));
      const copiedFiles = filesToCopy.map((file) => ({
        ...file,
        id: Date.now().toString() + Math.random(),
        name: file.name + " (Copy)",
        folder: destinationPath,
        modified: new Date().toISOString(),
        created: new Date().toISOString(),
      }));
      setFiles([...files, ...copiedFiles]);
      setSelectedFiles(new Set());
    },
    [files, selectedFiles]
  );

  // Clipboard operations
  const handleClipboardOperation = useCallback(
    (operation) => {
      switch (operation) {
        case "copy":
          const selectedFilesList = files.filter((file) =>
            selectedFiles.has(file.id)
          );
          setClipboard({
            files: selectedFilesList,
            operation: "copy",
          });
          break;

        case "cut":
          const selectedFilesListCut = files.filter((file) =>
            selectedFiles.has(file.id)
          );
          setClipboard({
            files: selectedFilesListCut,
            operation: "cut",
          });
          // Mark files as "cut" (could add visual indication)
          setFiles(
            files.map((file) =>
              selectedFiles.has(file.id) ? { ...file, isCut: true } : file
            )
          );
          break;

        case "paste":
          if (clipboard.files.length === 0) return;

          if (clipboard.operation === "copy") {
            // Copy files to current folder
            const copiedFiles = clipboard.files.map((file) => ({
              ...file,
              id: Date.now().toString() + Math.random(),
              name: file.name + " (Copy)",
              folder: currentFolder,
              modified: new Date().toISOString(),
              created: new Date().toISOString(),
              isCut: false,
            }));
            setFiles([...files, ...copiedFiles]);
          } else if (clipboard.operation === "cut") {
            // Move files to current folder
            setFiles(
              files.map((file) => {
                if (
                  clipboard.files.some((clipFile) => clipFile.id === file.id)
                ) {
                  return {
                    ...file,
                    folder: currentFolder,
                    modified: new Date().toISOString(),
                    isCut: false,
                  };
                }
                return file;
              })
            );
          }

          // Clear clipboard
          setClipboard({ files: [], operation: null });
          setSelectedFiles(new Set());
          break;
      }
    },
    [files, selectedFiles, clipboard, currentFolder]
  );

  // File upload handler
  const handleFileUpload = useCallback(
    (uploadedFiles, targetFolder = currentFolder) => {
      const newFiles = Array.from(uploadedFiles).map((file, index) => {
        const fileType = getFileType(file.name, file.type);

        return {
          id: (Date.now() + index).toString(),
          name: file.name,
          type: fileType,
          size: formatFileSize(file.size),
          sizeBytes: file.size,
          modified: new Date().toISOString(),
          created: new Date().toISOString(),
          owner: "You",
          folder: targetFolder,
          starred: false,
          shared: false,
          downloads: 0,
          thumbnail: null,
          description: "",
          tags: [],
          permissions: ["read", "write", "share"],
          processing: "uploading",
          progress: 0,
        };
      });

      setFiles([...files, ...newFiles]);

      // Simulate upload progress
      newFiles.forEach((file, index) => {
        let progress = 0;
        const interval = setInterval(() => {
          progress += Math.random() * 20;
          if (progress >= 100) {
            progress = 100;
            clearInterval(interval);
            // Remove processing state
            setFiles((prevFiles) =>
              prevFiles.map((f) =>
                f.id === file.id
                  ? { ...f, processing: null, progress: null }
                  : f
              )
            );
          } else {
            setFiles((prevFiles) =>
              prevFiles.map((f) => (f.id === file.id ? { ...f, progress } : f))
            );
          }
        }, 200);
      });
    },
    [files, currentFolder]
  );
  // Add this new function to useFileManager.js
  const handleDragMoveFile = useCallback((fileId, destinationPath) => {
    setFiles((prevFiles) =>
      prevFiles.map((file) =>
        file.id === fileId
          ? {
              ...file,
              folder: destinationPath,
              modified: new Date().toISOString(),
            }
          : file
      )
    );
  }, []);
  // Helper functions
  const getFileType = (fileName, mimeType) => {
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
        return "archive";
      case "mp3":
      case "wav":
      case "flac":
      case "aac":
        return "audio";
      case "mp4":
      case "avi":
      case "mkv":
      case "mov":
        return "video";
      case "jpg":
      case "jpeg":
      case "png":
      case "gif":
      case "svg":
        return "image";
      default:
        return "document";
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0 || isNaN(bytes)) return "0 KB";
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + " " + sizes[i];
  };

  return {
    // State
    viewMode,
    setViewMode,
    searchQuery,
    setSearchQuery,
    selectedFiles,
    setSelectedFiles,
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
    folders,
    folderManifest,
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
    handleEmptySpaceContextMenu,

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
    handleClipboardOperation,
    updateFolderManifest,
    handleFileUpload,
    handleDragMoveFile,
  };
}
