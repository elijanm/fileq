// components/FileManager/components/FileUploadZone.jsx
import React, { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Upload, X, FileIcon, CheckCircle } from "lucide-react";

export default function FileUploadZone({
  onFileUpload,
  currentFolder,
  className = "",
}) {
  const [dragActive, setDragActive] = useState(false);
  const [uploadQueue, setUploadQueue] = useState([]);
  const fileInputRef = useRef(null);

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
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFiles(e.target.files);
    }
  };

  const handleFiles = (files) => {
    const fileList = Array.from(files);

    // Add files to upload queue
    const queueItems = fileList.map((file) => ({
      id: Date.now() + Math.random(),
      file,
      status: "pending", // pending, uploading, completed, error
      progress: 0,
    }));

    setUploadQueue((prev) => [...prev, ...queueItems]);

    // Start upload process
    queueItems.forEach((item) => {
      uploadFile(item);
    });

    // Call the parent handler
    onFileUpload(files, currentFolder);
  };

  const uploadFile = async (queueItem) => {
    setUploadQueue((prev) =>
      prev.map((item) =>
        item.id === queueItem.id ? { ...item, status: "uploading" } : item
      )
    );

    // Simulate upload progress
    const uploadInterval = setInterval(() => {
      setUploadQueue((prev) =>
        prev.map((item) => {
          if (item.id === queueItem.id && item.status === "uploading") {
            const newProgress = Math.min(
              item.progress + Math.random() * 25,
              100
            );
            return {
              ...item,
              progress: newProgress,
              status: newProgress >= 100 ? "completed" : "uploading",
            };
          }
          return item;
        })
      );
    }, 200);

    // Clear interval after completion
    setTimeout(() => {
      clearInterval(uploadInterval);
      setUploadQueue((prev) =>
        prev.map((item) =>
          item.id === queueItem.id
            ? { ...item, status: "completed", progress: 100 }
            : item
        )
      );

      // Remove from queue after 2 seconds
      setTimeout(() => {
        setUploadQueue((prev) =>
          prev.filter((item) => item.id !== queueItem.id)
        );
      }, 2000);
    }, 2000 + Math.random() * 2000);
  };

  const removeFromQueue = (itemId) => {
    setUploadQueue((prev) => prev.filter((item) => item.id !== itemId));
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <>
      {/* Main upload zone */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-all mb-6 ${
          dragActive
            ? "border-blue-500 bg-blue-50"
            : "border-slate-300 hover:border-slate-400"
        } ${className}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
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
        <Button className="bg-blue-600 hover:bg-blue-700">
          <Upload className="w-4 h-4 mr-2" />
          Choose Files
        </Button>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleChange}
          className="hidden"
        />
      </div>

      {/* Upload queue */}
      {uploadQueue.length > 0 && (
        <div className="mb-6">
          <h4 className="text-sm font-medium text-slate-700 mb-3">
            Uploading Files ({uploadQueue.length})
          </h4>
          <div className="space-y-2">
            {uploadQueue.map((item) => (
              <div
                key={item.id}
                className="flex items-center space-x-3 p-3 bg-white border rounded-lg shadow-sm"
              >
                <div className="flex-shrink-0">
                  {item.status === "completed" ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : (
                    <FileIcon className="w-5 h-5 text-slate-400" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-900 truncate">
                      {item.file.name}
                    </p>
                    <button
                      onClick={() => removeFromQueue(item.id)}
                      className="text-slate-400 hover:text-slate-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <p className="text-xs text-slate-500">
                    {formatFileSize(item.file.size)}
                    {item.status === "uploading" &&
                      ` • ${Math.round(item.progress)}%`}
                    {item.status === "completed" && " • Completed"}
                  </p>

                  {item.status === "uploading" && (
                    <div className="mt-2 w-full bg-gray-200 rounded-full h-1.5">
                      <div
                        className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${item.progress}%` }}
                      ></div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
