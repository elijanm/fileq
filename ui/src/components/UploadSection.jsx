// components/UploadSection.jsx
import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Upload, AlertCircle } from "lucide-react";

export default function UploadSection({
  uploading,
  uploadProgress,
  fileInfo,
  error,
  dragActive,
  inputRef,
  onDrag,
  onDrop,
  onFileSelect,
}) {
  return (
    <div className="max-w-2xl mx-auto">
      <Card className="border-2 border-dashed border-indigo-200 bg-gradient-to-br from-indigo-50/50 to-purple-50/50 backdrop-blur-sm">
        <CardContent className="p-12">
          <div
            className={`border-2 border-dashed rounded-2xl p-16 text-center transition-all duration-300 ${
              dragActive
                ? "border-indigo-400 bg-indigo-100/50 scale-105"
                : "border-indigo-300 hover:border-indigo-400 hover:bg-indigo-50/30"
            }`}
            onDragEnter={onDrag}
            onDragLeave={onDrag}
            onDragOver={onDrag}
            onDrop={onDrop}
          >
            {!uploading && (
              <>
                <div className="w-20 h-20 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-3xl flex items-center justify-center mx-auto mb-8 shadow-lg">
                  <Upload className="w-10 h-10 text-white" />
                </div>
                <h3 className="text-3xl font-bold text-slate-900 mb-4">
                  Drop your files here
                </h3>
                <p className="text-slate-600 mb-10 text-lg">
                  Or click to browse • All formats supported • 3GB max for free
                  users
                </p>
                <Button
                  onClick={() => inputRef.current?.click()}
                  size="lg"
                  className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-xl px-10 py-4 text-lg"
                  disabled={uploading}
                >
                  <Upload className="w-6 h-6 mr-3" />
                  Choose Files
                </Button>
                <input
                  ref={inputRef}
                  type="file"
                  className="hidden"
                  onChange={onFileSelect}
                />
              </>
            )}

            {uploading && (
              <div className="space-y-8">
                <div className="w-20 h-20 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-3xl flex items-center justify-center mx-auto">
                  <Upload className="w-10 h-10 text-white animate-pulse" />
                </div>
                <div>
                  <p className="text-2xl font-semibold text-slate-900 mb-6">
                    Uploading {fileInfo?.name}...
                  </p>
                  <Progress
                    value={uploadProgress}
                    className="w-full h-4 bg-slate-200"
                  />
                  <p className="text-slate-600 mt-4 text-lg">
                    {Math.round(uploadProgress)}% complete
                  </p>
                </div>
              </div>
            )}
          </div>

          {error && (
            <Alert className="mt-8 border-red-200 bg-red-50">
              <AlertCircle className="h-5 w-5 text-red-600" />
              <AlertTitle className="text-red-800">Upload Error</AlertTitle>
              <AlertDescription className="text-red-700">
                {error}
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
