// components/FileManager/components/CreateFolderModal.jsx
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { X, FolderPlus, AlertCircle } from "lucide-react";

export default function CreateFolderModal({
  isOpen,
  onClose,
  onCreateFolder,
  currentFolder,
}) {
  const [folderName, setFolderName] = useState("");
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const validateFolderName = (name) => {
    if (!name.trim()) return "Folder name cannot be empty";
    if (name.length > 255) return "Folder name too long";
    if (/[<>:"/\\|?*\x00-\x1f]/.test(name))
      return "Invalid characters in folder name";
    if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i.test(name))
      return "Reserved folder name";
    return null;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const validationError = validateFolderName(folderName);

    if (validationError) {
      setError(validationError);
      return;
    }

    onCreateFolder(folderName.trim());
    setFolderName("");
    setError("");
    onClose();
  };

  const handleInputChange = (e) => {
    const value = e.target.value;
    setFolderName(value);

    if (error) {
      const validationError = validateFolderName(value);
      setError(validationError || "");
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <Card className="w-full max-w-md mx-4">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center text-lg">
              <FolderPlus className="w-5 h-5 mr-2 text-blue-600" />
              Create New Folder
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="w-4 h-4" />
            </Button>
          </div>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Folder Name
              </label>
              <input
                type="text"
                value={folderName}
                onChange={handleInputChange}
                placeholder="Enter folder name"
                className={`w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                  error ? "border-red-300" : "border-slate-200"
                }`}
                autoFocus
              />
              {error && (
                <div className="mt-2 flex items-center text-sm text-red-600">
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {error}
                </div>
              )}
            </div>

            <div className="text-sm text-slate-500">
              Creating in:{" "}
              <span className="font-medium">{currentFolder || "/"}</span>
            </div>

            <div className="flex justify-end space-x-3 pt-4">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!folderName.trim() || !!error}
                className="bg-blue-600 hover:bg-blue-700"
              >
                <FolderPlus className="w-4 h-4 mr-2" />
                Create Folder
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
