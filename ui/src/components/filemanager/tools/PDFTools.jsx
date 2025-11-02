// components/FileManager/components/tools/PDFTools.jsx
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  FileText,
  Scissors,
  Combine,
  RotateCw,
  CombineIcon as Compress,
  Lock,
  Unlock,
  Type,
  Search,
  Download,
  Upload,
  Eye,
  Layers,
} from "lucide-react";

export default function PDFTools({ file }) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedTool, setSelectedTool] = useState(null);

  const tools = [
    {
      id: "split",
      name: "Split PDF",
      description: "Split PDF into separate pages or sections",
      icon: Scissors,
      color: "text-red-600",
      bgColor: "bg-red-50",
    },
    {
      id: "merge",
      name: "Merge PDFs",
      description: "Combine multiple PDFs into one document",
      icon: Combine,
      color: "text-green-600",
      bgColor: "bg-green-50",
    },
    {
      id: "rotate",
      name: "Rotate Pages",
      description: "Rotate PDF pages clockwise or counterclockwise",
      icon: RotateCw,
      color: "text-blue-600",
      bgColor: "bg-blue-50",
    },
    {
      id: "compress",
      name: "Compress PDF",
      description: "Reduce file size while maintaining quality",
      icon: Compress,
      color: "text-purple-600",
      bgColor: "bg-purple-50",
    },
    {
      id: "password",
      name: "Password Protect",
      description: "Add password protection to your PDF",
      icon: Lock,
      color: "text-orange-600",
      bgColor: "bg-orange-50",
    },
    {
      id: "unlock",
      name: "Remove Password",
      description: "Remove password protection from PDF",
      icon: Unlock,
      color: "text-teal-600",
      bgColor: "bg-teal-50",
    },
    {
      id: "extract-text",
      name: "Extract Text",
      description: "Extract all text content from PDF",
      icon: Type,
      color: "text-indigo-600",
      bgColor: "bg-indigo-50",
    },
    {
      id: "search",
      name: "Search Content",
      description: "Search for specific text within PDF",
      icon: Search,
      color: "text-gray-600",
      bgColor: "bg-gray-50",
    },
  ];

  const handleToolSelect = (toolId) => {
    setSelectedTool(toolId);
    setIsProcessing(true);
    // Simulate processing
    setTimeout(() => {
      setIsProcessing(false);
      console.log(`Processing ${toolId} for file:`, file.name);
    }, 2000);
  };

  const renderToolInterface = () => {
    if (!selectedTool) return null;

    const tool = tools.find((t) => t.id === selectedTool);

    switch (selectedTool) {
      case "split":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Split PDF Options</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Split Method
                </label>
                <select className="w-full border border-gray-200 rounded-lg px-3 py-2">
                  <option>Split by page range</option>
                  <option>Split into individual pages</option>
                  <option>Split by bookmarks</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Page Range (e.g., 1-5, 10-15)
                </label>
                <input
                  type="text"
                  placeholder="1-10"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2"
                />
              </div>
              <Button className="w-full">Split PDF</Button>
            </CardContent>
          </Card>
        );

      case "merge":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Merge PDFs</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="border-2 border-dashed border-gray-200 rounded-lg p-6 text-center">
                <Upload className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                <p className="text-sm text-gray-600">
                  Drop additional PDF files here or click to browse
                </p>
                <Button variant="outline" className="mt-2">
                  Select Files
                </Button>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                  <span className="text-sm">{file.name}</span>
                  <span className="text-xs text-gray-500">Current file</span>
                </div>
              </div>
              <Button className="w-full" disabled>
                Add more files to merge
              </Button>
            </CardContent>
          </Card>
        );

      case "compress":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Compression Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Compression Level
                </label>
                <select className="w-full border border-gray-200 rounded-lg px-3 py-2">
                  <option>Low (High quality)</option>
                  <option>Medium (Balanced)</option>
                  <option>High (Small size)</option>
                </select>
              </div>
              <div className="bg-blue-50 p-3 rounded-lg">
                <p className="text-sm text-blue-700">
                  Current size: {file.size}
                </p>
                <p className="text-sm text-blue-700">
                  Estimated compressed size: ~1.8 MB
                </p>
              </div>
              <Button className="w-full">Compress PDF</Button>
            </CardContent>
          </Card>
        );

      case "password":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Password Protection</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Password
                </label>
                <input
                  type="password"
                  placeholder="Enter password"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Confirm Password
                </label>
                <input
                  type="password"
                  placeholder="Confirm password"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2"
                />
              </div>
              <div className="space-y-2">
                <label className="flex items-center">
                  <input type="checkbox" className="rounded mr-2" />
                  <span className="text-sm">Restrict printing</span>
                </label>
                <label className="flex items-center">
                  <input type="checkbox" className="rounded mr-2" />
                  <span className="text-sm">Restrict copying</span>
                </label>
                <label className="flex items-center">
                  <input type="checkbox" className="rounded mr-2" />
                  <span className="text-sm">Restrict editing</span>
                </label>
              </div>
              <Button className="w-full">Apply Password</Button>
            </CardContent>
          </Card>
        );

      default:
        return (
          <Card className="mt-4">
            <CardContent className="p-6 text-center">
              <tool.icon className="w-8 h-8 mx-auto text-gray-400 mb-2" />
              <p className="text-sm text-gray-600">
                {tool.name} tool interface coming soon...
              </p>
              <Button className="mt-4" onClick={() => setSelectedTool(null)}>
                Back to Tools
              </Button>
            </CardContent>
          </Card>
        );
    }
  };

  return (
    <div className="space-y-4">
      <div className="text-center">
        <FileText className="w-12 h-12 mx-auto text-red-600 mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">PDF Tools</h3>
        <p className="text-sm text-gray-600">
          Professional PDF editing and management tools
        </p>
      </div>

      {/* File Info */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{file.name}</p>
              <p className="text-sm text-gray-500">{file.size}</p>
            </div>
            <Button size="sm" variant="outline">
              <Eye className="w-4 h-4 mr-2" />
              Preview
            </Button>
          </div>
        </CardContent>
      </Card>

      {!selectedTool && (
        <div className="grid grid-cols-1 gap-3">
          {tools.map((tool) => {
            const Icon = tool.icon;
            return (
              <Card
                key={tool.id}
                className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => handleToolSelect(tool.id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start space-x-3">
                    <div className={`p-2 rounded-lg ${tool.bgColor}`}>
                      <Icon className={`w-5 h-5 ${tool.color}`} />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-medium text-gray-900">{tool.name}</h4>
                      <p className="text-sm text-gray-600 mt-1">
                        {tool.description}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {isProcessing && (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-sm text-gray-600">Processing your request...</p>
        </div>
      )}

      {renderToolInterface()}
    </div>
  );
}
