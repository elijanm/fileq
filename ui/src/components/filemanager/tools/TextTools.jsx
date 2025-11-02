// components/FileManager/components/tools/TextTools.jsx
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  FileText,
  Edit3,
  Search,
  Type,
  Languages,
  BarChart3,
  CheckCircle,
  FileCode,
  Download,
  Upload,
  Copy,
  Eye,
  Save,
  FileCheck,
  Zap,
  BookOpen,
  Hash,
} from "lucide-react";

export default function TextTools({ file }) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedTool, setSelectedTool] = useState(null);
  const [textContent, setTextContent] = useState("Loading text content...");

  const tools = [
    {
      id: "editor",
      name: "Text Editor",
      description: "Edit text content with syntax highlighting",
      icon: Edit3,
      color: "text-blue-600",
      bgColor: "bg-blue-50",
    },
    {
      id: "search",
      name: "Find & Replace",
      description: "Search and replace text with regex support",
      icon: Search,
      color: "text-green-600",
      bgColor: "bg-green-50",
    },
    {
      id: "format",
      name: "Format Text",
      description: "Auto-format and beautify code or text",
      icon: Type,
      color: "text-purple-600",
      bgColor: "bg-purple-50",
    },
    {
      id: "translate",
      name: "Translate",
      description: "Translate text to different languages",
      icon: Languages,
      color: "text-orange-600",
      bgColor: "bg-orange-50",
    },
    {
      id: "analyze",
      name: "Text Analysis",
      description: "Word count, readability, and statistics",
      icon: BarChart3,
      color: "text-indigo-600",
      bgColor: "bg-indigo-50",
    },
    {
      id: "spell",
      name: "Spell Check",
      description: "Check spelling and grammar",
      icon: CheckCircle,
      color: "text-green-500",
      bgColor: "bg-green-50",
    },
    {
      id: "convert",
      name: "Format Conversion",
      description: "Convert between text formats (MD, HTML, TXT)",
      icon: FileCode,
      color: "text-teal-600",
      bgColor: "bg-teal-50",
    },
    {
      id: "extract",
      name: "Extract Data",
      description: "Extract emails, URLs, or specific patterns",
      icon: Hash,
      color: "text-pink-600",
      bgColor: "bg-pink-50",
    },
  ];

  const handleToolSelect = (toolId) => {
    setSelectedTool(toolId);
    setIsProcessing(true);
    setTimeout(() => {
      setIsProcessing(false);
      console.log(`Processing ${toolId} for file:`, file.name);
    }, 1000);
  };

  const renderToolInterface = () => {
    if (!selectedTool) return null;

    const tool = tools.find((t) => t.id === selectedTool);

    switch (selectedTool) {
      case "editor":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Text Editor</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Syntax Highlighting
                  </label>
                  <select className="mt-1 border border-gray-200 rounded px-2 py-1 text-sm">
                    <option>Plain Text</option>
                    <option>JavaScript</option>
                    <option>Python</option>
                    <option>HTML</option>
                    <option>CSS</option>
                    <option>Markdown</option>
                    <option>JSON</option>
                  </select>
                </div>
                <div className="flex space-x-2">
                  <Button size="sm" variant="outline">
                    <Copy className="w-4 h-4 mr-1" />
                    Copy
                  </Button>
                  <Button size="sm">
                    <Save className="w-4 h-4 mr-1" />
                    Save
                  </Button>
                </div>
              </div>

              <textarea
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                className="w-full h-64 font-mono text-sm border border-gray-200 rounded-lg p-3 resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Your text content will appear here..."
              />

              <div className="flex justify-between text-xs text-gray-500">
                <span>Lines: 12 | Words: 245 | Characters: 1,438</span>
                <span>UTF-8 | LF</span>
              </div>
            </CardContent>
          </Card>
        );

      case "search":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Find & Replace</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Find
                </label>
                <input
                  type="text"
                  placeholder="Search text..."
                  className="w-full border border-gray-200 rounded-lg px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Replace with
                </label>
                <input
                  type="text"
                  placeholder="Replacement text..."
                  className="w-full border border-gray-200 rounded-lg px-3 py-2"
                />
              </div>

              <div className="space-y-2">
                <label className="flex items-center">
                  <input type="checkbox" className="rounded mr-2" />
                  <span className="text-sm">Case sensitive</span>
                </label>
                <label className="flex items-center">
                  <input type="checkbox" className="rounded mr-2" />
                  <span className="text-sm">Whole words only</span>
                </label>
                <label className="flex items-center">
                  <input type="checkbox" className="rounded mr-2" />
                  <span className="text-sm">Use regular expressions</span>
                </label>
              </div>

              <div className="flex space-x-2">
                <Button variant="outline" className="flex-1">
                  Find Next
                </Button>
                <Button className="flex-1">Replace All</Button>
              </div>
            </CardContent>
          </Card>
        );

      case "analyze":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Text Analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-4 bg-blue-50 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">1,247</div>
                  <div className="text-sm text-blue-600">Words</div>
                </div>
                <div className="text-center p-4 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">6,843</div>
                  <div className="text-sm text-green-600">Characters</div>
                </div>
                <div className="text-center p-4 bg-purple-50 rounded-lg">
                  <div className="text-2xl font-bold text-purple-600">67</div>
                  <div className="text-sm text-purple-600">Sentences</div>
                </div>
                <div className="text-center p-4 bg-orange-50 rounded-lg">
                  <div className="text-2xl font-bold text-orange-600">12</div>
                  <div className="text-sm text-orange-600">Paragraphs</div>
                </div>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Readability</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm">Flesch Reading Ease</span>
                      <span className="text-sm font-medium">67 (Standard)</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Grade Level</span>
                      <span className="text-sm font-medium">8th Grade</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Avg. Reading Time</span>
                      <span className="text-sm font-medium">4 min 58 sec</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Top Keywords</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {[
                      "technology",
                      "innovation",
                      "development",
                      "digital",
                      "future",
                    ].map((word) => (
                      <span
                        key={word}
                        className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded"
                      >
                        {word}
                      </span>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </CardContent>
          </Card>
        );

      case "translate":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Translate Text</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    From
                  </label>
                  <select className="w-full border border-gray-200 rounded-lg px-3 py-2">
                    <option>Auto-detect</option>
                    <option>English</option>
                    <option>Spanish</option>
                    <option>French</option>
                    <option>German</option>
                    <option>Chinese</option>
                    <option>Japanese</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    To
                  </label>
                  <select className="w-full border border-gray-200 rounded-lg px-3 py-2">
                    <option>Spanish</option>
                    <option>English</option>
                    <option>French</option>
                    <option>German</option>
                    <option>Chinese</option>
                    <option>Japanese</option>
                    <option>Swahili</option>
                  </select>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Original Text
                  </label>
                  <textarea
                    className="w-full h-24 border border-gray-200 rounded-lg p-3 resize-none"
                    placeholder="Text to translate..."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Translation
                  </label>
                  <div className="w-full h-24 border border-gray-200 rounded-lg p-3 bg-gray-50">
                    <p className="text-gray-500 text-sm">
                      Translation will appear here...
                    </p>
                  </div>
                </div>
              </div>

              <Button className="w-full">
                <Languages className="w-4 h-4 mr-2" />
                Translate Text
              </Button>
            </CardContent>
          </Card>
        );

      case "spell":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Spell & Grammar Check</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-green-50 p-4 rounded-lg">
                <div className="flex items-center mb-2">
                  <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                  <span className="font-medium text-green-800">
                    Check Complete
                  </span>
                </div>
                <p className="text-sm text-green-700">
                  Found 3 issues in your document
                </p>
              </div>

              <div className="space-y-3">
                <div className="border border-red-200 bg-red-50 rounded-lg p-3">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-sm font-medium text-red-800">
                      Spelling Error
                    </span>
                    <span className="text-xs text-red-600">Line 5</span>
                  </div>
                  <p className="text-sm text-red-700 mb-2">
                    "recieve" should be "receive"
                  </p>
                  <div className="flex space-x-2">
                    <Button size="sm" variant="outline">
                      Ignore
                    </Button>
                    <Button size="sm">Fix</Button>
                  </div>
                </div>

                <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-3">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-sm font-medium text-yellow-800">
                      Grammar
                    </span>
                    <span className="text-xs text-yellow-600">Line 12</span>
                  </div>
                  <p className="text-sm text-yellow-700 mb-2">
                    Consider using "who" instead of "that" for people
                  </p>
                  <div className="flex space-x-2">
                    <Button size="sm" variant="outline">
                      Ignore
                    </Button>
                    <Button size="sm">Fix</Button>
                  </div>
                </div>
              </div>

              <Button className="w-full" variant="outline">
                <Zap className="w-4 h-4 mr-2" />
                Fix All Issues
              </Button>
            </CardContent>
          </Card>
        );

      default:
        return (
          <Card className="mt-4">
            <CardContent className="p-6 text-center">
              <tool.icon className="w-8 h-8 mx-auto text-gray-400 mb-2" />
              <p className="text-sm text-gray-600">
                {tool.name} interface coming soon...
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
        <FileText className="w-12 h-12 mx-auto text-blue-600 mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Text Tools</h3>
        <p className="text-sm text-gray-600">
          Professional text editing and analysis tools
        </p>
      </div>

      {/* File Info */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="font-medium">{file.name}</p>
              <p className="text-sm text-gray-500">{file.size}</p>
            </div>
            <div className="flex space-x-2">
              <Button size="sm" variant="outline">
                <Eye className="w-4 h-4 mr-2" />
                Preview
              </Button>
              <Button size="sm" variant="outline">
                <Download className="w-4 h-4 mr-2" />
                Download
              </Button>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-lg font-semibold text-gray-900">1,247</div>
              <div className="text-xs text-gray-500">Words</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-gray-900">67</div>
              <div className="text-xs text-gray-500">Lines</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-gray-900">6.8KB</div>
              <div className="text-xs text-gray-500">Size</div>
            </div>
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
          <p className="text-sm text-gray-600">Processing your text...</p>
        </div>
      )}

      {renderToolInterface()}
    </div>
  );
}
