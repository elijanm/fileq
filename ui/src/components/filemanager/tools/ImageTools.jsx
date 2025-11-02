// components/FileManager/components/tools/ImageTools.jsx
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Image,
  Crop,
  RotateCw,
  CombineIcon as Compress,
  CropIcon as Resize,
  Palette,
  Zap,
  Maximize2,
  Download,
  FileImage,
  Layers,
  Filter,
  Sun,
  Contrast,
  Eye,
  RotateCcw,
  FlipHorizontal,
  FlipVertical,
  Scissors,
  Save,
  Undo,
  Redo,
} from "lucide-react";

export default function ImageTools({ file }) {
  const [selectedTool, setSelectedTool] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [imageAdjustments, setImageAdjustments] = useState({
    brightness: 0,
    contrast: 0,
    saturation: 0,
    hue: 0,
  });

  const tools = [
    {
      id: "resize",
      name: "Resize",
      description: "Change image dimensions",
      icon: Maximize2,
      color: "text-blue-600",
      bgColor: "bg-blue-50",
      category: "transform",
    },
    {
      id: "crop",
      name: "Crop",
      description: "Trim image to desired area",
      icon: Crop,
      color: "text-green-600",
      bgColor: "bg-green-50",
      category: "transform",
    },
    {
      id: "rotate",
      name: "Rotate",
      description: "Rotate and flip image",
      icon: RotateCw,
      color: "text-orange-600",
      bgColor: "bg-orange-50",
      category: "transform",
    },
    {
      id: "enhance",
      name: "Enhance",
      description: "Adjust colors and lighting",
      icon: Zap,
      color: "text-yellow-600",
      bgColor: "bg-yellow-50",
      category: "adjust",
    },
    {
      id: "filters",
      name: "Filters",
      description: "Apply artistic effects",
      icon: Filter,
      color: "text-purple-600",
      bgColor: "bg-purple-50",
      category: "effects",
    },
    {
      id: "compress",
      name: "Optimize",
      description: "Reduce file size",
      icon: Compress,
      color: "text-indigo-600",
      bgColor: "bg-indigo-50",
      category: "optimize",
    },
    {
      id: "convert",
      name: "Convert",
      description: "Change file format",
      icon: FileImage,
      color: "text-teal-600",
      bgColor: "bg-teal-50",
      category: "optimize",
    },
    {
      id: "background",
      name: "Background",
      description: "Remove or replace background",
      icon: Layers,
      color: "text-pink-600",
      bgColor: "bg-pink-50",
      category: "effects",
    },
  ];

  const handleToolSelect = (toolId) => {
    setSelectedTool(toolId);
    setIsProcessing(true);
    setTimeout(() => {
      setIsProcessing(false);
    }, 1000);
  };

  const handleAdjustmentChange = (adjustment, value) => {
    setImageAdjustments({
      ...imageAdjustments,
      [adjustment]: value,
    });
  };

  const renderToolInterface = () => {
    if (!selectedTool) return null;

    switch (selectedTool) {
      case "resize":
        return <ResizeTool file={file} onBack={() => setSelectedTool(null)} />;
      case "crop":
        return <CropTool file={file} onBack={() => setSelectedTool(null)} />;
      case "rotate":
        return <RotateTool file={file} onBack={() => setSelectedTool(null)} />;
      case "enhance":
        return (
          <EnhanceTool
            file={file}
            adjustments={imageAdjustments}
            onAdjustmentChange={handleAdjustmentChange}
            onBack={() => setSelectedTool(null)}
          />
        );
      case "filters":
        return <FiltersTool file={file} onBack={() => setSelectedTool(null)} />;
      case "compress":
        return (
          <CompressTool file={file} onBack={() => setSelectedTool(null)} />
        );
      case "convert":
        return <ConvertTool file={file} onBack={() => setSelectedTool(null)} />;
      case "background":
        return (
          <BackgroundTool file={file} onBack={() => setSelectedTool(null)} />
        );
      default:
        return null;
    }
  };

  if (selectedTool) {
    return renderToolInterface();
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <Image className="w-12 h-12 mx-auto text-green-600 mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Image Tools
        </h3>
        <p className="text-sm text-gray-600">
          Professional image editing and optimization
        </p>
      </div>

      {/* Image Preview */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="font-medium">{file.name}</p>
              <p className="text-sm text-gray-500">
                {file.resolution || "1920×1080"} • {file.size}
              </p>
            </div>
            <Button size="sm" variant="outline">
              <Eye className="w-4 h-4 mr-2" />
              Preview
            </Button>
          </div>

          <div className="aspect-video bg-gradient-to-br from-gray-100 to-gray-200 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-300">
            <div className="text-center text-gray-500">
              <Image className="w-16 h-16 mx-auto mb-2 opacity-50" />
              <p className="text-sm">Image Preview</p>
              <p className="text-xs text-gray-400 mt-1">
                Click a tool below to start editing
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tools Grid */}
      <div className="grid grid-cols-2 gap-3">
        {tools.map((tool) => {
          const Icon = tool.icon;
          return (
            <Card
              key={tool.id}
              className="cursor-pointer hover:shadow-md transition-all duration-200 hover:-translate-y-1"
              onClick={() => handleToolSelect(tool.id)}
            >
              <CardContent className="p-4">
                <div className="text-center">
                  <div
                    className={`inline-flex p-3 rounded-xl ${tool.bgColor} mb-3`}
                  >
                    <Icon className={`w-6 h-6 ${tool.color}`} />
                  </div>
                  <h4 className="font-medium text-gray-900 mb-1">
                    {tool.name}
                  </h4>
                  <p className="text-xs text-gray-600">{tool.description}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {isProcessing && (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600 mx-auto mb-4"></div>
          <p className="text-sm text-gray-600">Loading tool...</p>
        </div>
      )}
    </div>
  );
}

// Individual Tool Components

const ResizeTool = ({ file, onBack }) => {
  const [dimensions, setDimensions] = useState({
    width: 1920,
    height: 1080,
    maintainRatio: true,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Resize Image</h3>
        <Button variant="ghost" onClick={onBack}>
          ← Back
        </Button>
      </div>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Width (px)
              </label>
              <input
                type="number"
                value={dimensions.width}
                onChange={(e) =>
                  setDimensions({
                    ...dimensions,
                    width: parseInt(e.target.value),
                  })
                }
                className="w-full border border-gray-200 rounded-lg px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Height (px)
              </label>
              <input
                type="number"
                value={dimensions.height}
                onChange={(e) =>
                  setDimensions({
                    ...dimensions,
                    height: parseInt(e.target.value),
                  })
                }
                className="w-full border border-gray-200 rounded-lg px-3 py-2"
              />
            </div>
          </div>

          <label className="flex items-center">
            <input
              type="checkbox"
              checked={dimensions.maintainRatio}
              onChange={(e) =>
                setDimensions({
                  ...dimensions,
                  maintainRatio: e.target.checked,
                })
              }
              className="rounded mr-2"
            />
            <span className="text-sm">Maintain aspect ratio</span>
          </label>

          <div className="bg-blue-50 p-3 rounded-lg">
            <p className="text-sm text-blue-700">
              Current: {file.resolution || "1920×1080"} • {file.size}
            </p>
            <p className="text-sm text-blue-700">
              New: {dimensions.width}×{dimensions.height} • ~1.2 MB (estimated)
            </p>
          </div>

          <Button className="w-full bg-blue-600 hover:bg-blue-700">
            <Maximize2 className="w-4 h-4 mr-2" />
            Resize Image
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

const CropTool = ({ file, onBack }) => {
  const [cropSettings, setCropSettings] = useState({
    x: 0,
    y: 0,
    width: 800,
    height: 600,
    aspectRatio: "free",
  });

  const aspectRatios = [
    { id: "free", label: "Free Form" },
    { id: "1:1", label: "Square (1:1)" },
    { id: "4:3", label: "Standard (4:3)" },
    { id: "16:9", label: "Widescreen (16:9)" },
    { id: "3:2", label: "Photo (3:2)" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Crop Image</h3>
        <Button variant="ghost" onClick={onBack}>
          ← Back
        </Button>
      </div>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Aspect Ratio
            </label>
            <select
              value={cropSettings.aspectRatio}
              onChange={(e) =>
                setCropSettings({
                  ...cropSettings,
                  aspectRatio: e.target.value,
                })
              }
              className="w-full border border-gray-200 rounded-lg px-3 py-2"
            >
              {aspectRatios.map((ratio) => (
                <option key={ratio.id} value={ratio.id}>
                  {ratio.label}
                </option>
              ))}
            </select>
          </div>

          <div className="bg-gray-100 p-4 rounded-lg">
            <div className="aspect-video bg-gray-300 rounded relative overflow-hidden">
              <div className="absolute inset-4 border-2 border-dashed border-blue-500 bg-blue-50 bg-opacity-50 flex items-center justify-center">
                <span className="text-blue-600 text-sm font-medium">
                  Crop Area
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-2">
            <div>
              <label className="block text-xs text-gray-600 mb-1">X</label>
              <input
                type="number"
                value={cropSettings.x}
                onChange={(e) =>
                  setCropSettings({
                    ...cropSettings,
                    x: parseInt(e.target.value),
                  })
                }
                className="w-full text-xs border rounded px-2 py-1"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Y</label>
              <input
                type="number"
                value={cropSettings.y}
                onChange={(e) =>
                  setCropSettings({
                    ...cropSettings,
                    y: parseInt(e.target.value),
                  })
                }
                className="w-full text-xs border rounded px-2 py-1"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Width</label>
              <input
                type="number"
                value={cropSettings.width}
                onChange={(e) =>
                  setCropSettings({
                    ...cropSettings,
                    width: parseInt(e.target.value),
                  })
                }
                className="w-full text-xs border rounded px-2 py-1"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Height</label>
              <input
                type="number"
                value={cropSettings.height}
                onChange={(e) =>
                  setCropSettings({
                    ...cropSettings,
                    height: parseInt(e.target.value),
                  })
                }
                className="w-full text-xs border rounded px-2 py-1"
              />
            </div>
          </div>

          <Button className="w-full bg-green-600 hover:bg-green-700">
            <Crop className="w-4 h-4 mr-2" />
            Apply Crop
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

const RotateTool = ({ file, onBack }) => {
  const [rotation, setRotation] = useState(0);

  const quickRotations = [
    { angle: 90, label: "90° Right", icon: RotateCw },
    { angle: -90, label: "90° Left", icon: RotateCcw },
    { angle: 180, label: "180°", icon: RotateCw },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Rotate & Flip</h3>
        <Button variant="ghost" onClick={onBack}>
          ← Back
        </Button>
      </div>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Custom Rotation
            </label>
            <div className="flex items-center space-x-4">
              <input
                type="range"
                min="-180"
                max="180"
                value={rotation}
                onChange={(e) => setRotation(parseInt(e.target.value))}
                className="flex-1"
              />
              <span className="text-sm font-medium w-12">{rotation}°</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Quick Rotations
            </label>
            <div className="grid grid-cols-3 gap-2">
              {quickRotations.map((rot) => {
                const Icon = rot.icon;
                return (
                  <Button
                    key={rot.angle}
                    variant="outline"
                    onClick={() => setRotation(rot.angle)}
                    className="flex flex-col items-center py-3"
                  >
                    <Icon className="w-5 h-5 mb-1" />
                    <span className="text-xs">{rot.label}</span>
                  </Button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Flip Options
            </label>
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="outline"
                className="flex items-center justify-center py-3"
              >
                <FlipHorizontal className="w-4 h-4 mr-2" />
                Flip Horizontal
              </Button>
              <Button
                variant="outline"
                className="flex items-center justify-center py-3"
              >
                <FlipVertical className="w-4 h-4 mr-2" />
                Flip Vertical
              </Button>
            </div>
          </div>

          <Button className="w-full bg-orange-600 hover:bg-orange-700">
            <RotateCw className="w-4 h-4 mr-2" />
            Apply Rotation
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

const EnhanceTool = ({ file, adjustments, onAdjustmentChange, onBack }) => {
  const controls = [
    { key: "brightness", label: "Brightness", icon: Sun, min: -100, max: 100 },
    { key: "contrast", label: "Contrast", icon: Contrast, min: -100, max: 100 },
    {
      key: "saturation",
      label: "Saturation",
      icon: Palette,
      min: -100,
      max: 100,
    },
    { key: "hue", label: "Hue", icon: Palette, min: -180, max: 180 },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Enhance Colors</h3>
        <Button variant="ghost" onClick={onBack}>
          ← Back
        </Button>
      </div>

      <Card>
        <CardContent className="p-6 space-y-6">
          {controls.map((control) => {
            const Icon = control.icon;
            return (
              <div key={control.key}>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-gray-700 flex items-center">
                    <Icon className="w-4 h-4 mr-2" />
                    {control.label}
                  </label>
                  <span className="text-sm text-gray-500">
                    {adjustments[control.key]}
                    {control.key === "hue" ? "°" : ""}
                  </span>
                </div>
                <input
                  type="range"
                  min={control.min}
                  max={control.max}
                  value={adjustments[control.key]}
                  onChange={(e) =>
                    onAdjustmentChange(control.key, parseInt(e.target.value))
                  }
                  className="w-full"
                />
              </div>
            );
          })}

          <div className="flex space-x-2 pt-4">
            <Button variant="outline" className="flex-1">
              <Undo className="w-4 h-4 mr-2" />
              Reset
            </Button>
            <Button className="flex-1 bg-yellow-600 hover:bg-yellow-700">
              <Zap className="w-4 h-4 mr-2" />
              Apply
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

const FiltersTool = ({ file, onBack }) => {
  const filters = [
    { id: "none", name: "Original", preview: "bg-gray-200" },
    { id: "bw", name: "Black & White", preview: "bg-gray-600" },
    { id: "sepia", name: "Sepia", preview: "bg-yellow-600" },
    { id: "vintage", name: "Vintage", preview: "bg-orange-400" },
    { id: "cool", name: "Cool", preview: "bg-blue-400" },
    { id: "warm", name: "Warm", preview: "bg-red-400" },
  ];

  const [selectedFilter, setSelectedFilter] = useState("none");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Apply Filters</h3>
        <Button variant="ghost" onClick={onBack}>
          ← Back
        </Button>
      </div>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {filters.map((filter) => (
              <div
                key={filter.id}
                className={`cursor-pointer border-2 rounded-lg p-3 transition-all ${
                  selectedFilter === filter.id
                    ? "border-purple-500 shadow-md"
                    : "border-gray-200 hover:border-gray-300"
                }`}
                onClick={() => setSelectedFilter(filter.id)}
              >
                <div
                  className={`w-full h-12 ${filter.preview} rounded mb-2 flex items-center justify-center`}
                >
                  <Image className="w-4 h-4 text-white opacity-75" />
                </div>
                <p className="text-xs text-center font-medium">{filter.name}</p>
              </div>
            ))}
          </div>

          {selectedFilter !== "none" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Filter Intensity
              </label>
              <input type="range" className="w-full" defaultValue="75" />
            </div>
          )}

          <Button className="w-full bg-purple-600 hover:bg-purple-700">
            <Filter className="w-4 h-4 mr-2" />
            Apply Filter
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

const CompressTool = ({ file, onBack }) => {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Optimize Size</h3>
        <Button variant="ghost" onClick={onBack}>
          ← Back
        </Button>
      </div>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Quality Level
            </label>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2">
              <option>High Quality (90%)</option>
              <option>Medium Quality (75%)</option>
              <option>Low Quality (50%)</option>
              <option>Custom</option>
            </select>
          </div>

          <div className="bg-indigo-50 p-4 rounded-lg">
            <p className="text-sm text-indigo-700 mb-1">
              Current size: {file.size}
            </p>
            <p className="text-sm text-indigo-700">
              Optimized size: ~800 KB (65% reduction)
            </p>
          </div>

          <Button className="w-full bg-indigo-600 hover:bg-indigo-700">
            <Compress className="w-4 h-4 mr-2" />
            Optimize Image
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

const ConvertTool = ({ file, onBack }) => {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Convert Format</h3>
        <Button variant="ghost" onClick={onBack}>
          ← Back
        </Button>
      </div>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Output Format
            </label>
            <select className="w-full border border-gray-200 rounded-lg px-3 py-2">
              <option>JPEG (.jpg)</option>
              <option>PNG (.png)</option>
              <option>WebP (.webp)</option>
              <option>GIF (.gif)</option>
              <option>BMP (.bmp)</option>
            </select>
          </div>

          <div className="bg-teal-50 p-4 rounded-lg">
            <p className="text-sm text-teal-700">
              Converting from PNG to JPEG will reduce file size but may lose
              transparency.
            </p>
          </div>

          <Button className="w-full bg-teal-600 hover:bg-teal-700">
            <FileImage className="w-4 h-4 mr-2" />
            Convert Format
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

const BackgroundTool = ({ file, onBack }) => {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Background Tools</h3>
        <Button variant="ghost" onClick={onBack}>
          ← Back
        </Button>
      </div>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Button
              variant="outline"
              className="h-20 flex flex-col items-center"
            >
              <Scissors className="w-6 h-6 mb-1" />
              <span className="text-sm">Remove Background</span>
            </Button>
            <Button
              variant="outline"
              className="h-20 flex flex-col items-center"
            >
              <Palette className="w-6 h-6 mb-1" />
              <span className="text-sm">Replace Background</span>
            </Button>
          </div>

          <div className="bg-pink-50 p-4 rounded-lg">
            <p className="text-sm text-pink-700">
              AI-powered background removal will automatically detect the main
              subject.
            </p>
          </div>

          <Button className="w-full bg-pink-600 hover:bg-pink-700">
            <Layers className="w-4 h-4 mr-2" />
            Process Background
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};
