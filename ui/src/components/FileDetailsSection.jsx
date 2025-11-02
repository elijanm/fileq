// components/FileDetailsSection.jsx
import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Check, Copy } from "lucide-react";

export default function FileDetailsSection({ fileInfo, downloadUrl, onReset }) {
  const formatFileSize = (bytes) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(downloadUrl);
  };

  return (
    <div className="space-y-6">
      <Card className="border-2 border-green-200 bg-gradient-to-br from-green-50 to-emerald-50">
        <CardContent className="p-8">
          <div className="flex items-center space-x-4 mb-6">
            <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center">
              <Check className="w-8 h-8 text-green-600" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-slate-900">
                Upload Complete!
              </h2>
              <p className="text-green-700">File processed successfully</p>
            </div>
          </div>

          {/* File Information */}
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-slate-600">
                File Name
              </label>
              <p className="text-lg font-semibold text-slate-900">
                {fileInfo?.name}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-slate-600">
                  File Size
                </label>
                <p className="text-slate-900 font-medium">
                  {formatFileSize(fileInfo?.size)}
                </p>
              </div>
              <div>
                <label className="text-sm font-medium text-slate-600">
                  File Type
                </label>
                <p className="text-slate-900 font-medium">
                  {fileInfo?.type || "Unknown"}
                </p>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-slate-600">
                Uploaded
              </label>
              <p className="text-slate-900 font-medium">
                {formatDate(fileInfo?.lastModified)}
              </p>
            </div>

            {/* Download Link */}
            <div className="pt-4 border-t border-green-200">
              <label className="text-sm font-medium text-slate-600 mb-2 block">
                Download Link
              </label>
              <div className="flex gap-2">
                <Input
                  value={downloadUrl}
                  readOnly
                  className="text-sm bg-white"
                />
                <Button
                  size="sm"
                  onClick={copyToClipboard}
                  variant="outline"
                  className="border-green-300 hover:bg-green-50"
                >
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Actions */}
            <div className="pt-4 space-y-2">
              <Button onClick={onReset} variant="outline" className="w-full">
                Upload Another File
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
