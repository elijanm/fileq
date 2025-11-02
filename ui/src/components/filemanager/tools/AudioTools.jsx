// components/FileManager/components/tools/AudioTools.jsx
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Headphones,
  Mic,
  Music,
  DollarSign,
  Scissors,
  Volume2,
  Repeat,
  Download,
  Upload,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Zap,
  FileAudio,
  WavesIcon as Waveform,
} from "lucide-react";

export default function AudioTools({ file }) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedTool, setSelectedTool] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const tools = [
    {
      id: "transcribe",
      name: "Transcribe Audio",
      description: "Convert speech to text using AI",
      icon: Mic,
      color: "text-blue-600",
      bgColor: "bg-blue-50",
    },
    {
      id: "trim",
      name: "Trim & Cut",
      description: "Cut and trim audio segments",
      icon: Scissors,
      color: "text-red-600",
      bgColor: "bg-red-50",
    },
    {
      id: "enhance",
      name: "Audio Enhancement",
      description: "Reduce noise and improve quality",
      icon: Zap,
      color: "text-yellow-600",
      bgColor: "bg-yellow-50",
    },
    {
      id: "convert",
      name: "Format Conversion",
      description: "Convert between audio formats",
      icon: FileAudio,
      color: "text-green-600",
      bgColor: "bg-green-50",
    },
    {
      id: "volume",
      name: "Volume Control",
      description: "Adjust audio volume and normalize",
      icon: Volume2,
      color: "text-purple-600",
      bgColor: "bg-purple-50",
    },
    {
      id: "remix",
      name: "Remix & Edit",
      description: "Professional audio remixing tools",
      icon: Music,
      color: "text-pink-600",
      bgColor: "bg-pink-50",
    },
    {
      id: "ringtone",
      name: "Create Ringtone",
      description: "Convert to mobile ringtone formats",
      icon: Repeat,
      color: "text-indigo-600",
      bgColor: "bg-indigo-50",
    },
    {
      id: "monetize",
      name: "Monetize (Skiza)",
      description: "Prepare for Skiza tone distribution",
      icon: DollarSign,
      color: "text-emerald-600",
      bgColor: "bg-emerald-50",
    },
  ];

  const handleToolSelect = (toolId) => {
    setSelectedTool(toolId);
    setIsProcessing(true);
    setTimeout(() => {
      setIsProcessing(false);
      console.log(`Processing ${toolId} for file:`, file.name);
    }, 2000);
  };

  const renderToolInterface = () => {
    if (!selectedTool) return null;

    const tool = tools.find((t) => t.id === selectedTool);

    switch (selectedTool) {
      case "transcribe":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Audio Transcription</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Language
                </label>
                <select className="w-full border border-gray-200 rounded-lg px-3 py-2">
                  <option>English</option>
                  <option>Spanish</option>
                  <option>French</option>
                  <option>German</option>
                  <option>Swahili</option>
                  <option>Auto-detect</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    className="rounded mr-2"
                    defaultChecked
                  />
                  <span className="text-sm">Include timestamps</span>
                </label>
                <label className="flex items-center">
                  <input type="checkbox" className="rounded mr-2" />
                  <span className="text-sm">Speaker identification</span>
                </label>
                <label className="flex items-center">
                  <input type="checkbox" className="rounded mr-2" />
                  <span className="text-sm">Export to SRT format</span>
                </label>
              </div>
              <Button className="w-full">Start Transcription</Button>
            </CardContent>
          </Card>
        );

      case "trim":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Trim Audio</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Audio Waveform Placeholder */}
              <div className="bg-gray-100 p-4 rounded-lg">
                <div className="flex items-center justify-center h-20 bg-blue-50 rounded">
                  <Waveform className="w-8 h-8 text-blue-400" />
                  <span className="ml-2 text-sm text-blue-600">
                    Audio Waveform
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Start Time
                  </label>
                  <input
                    type="text"
                    placeholder="00:00:00"
                    className="w-full border border-gray-200 rounded-lg px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    End Time
                  </label>
                  <input
                    type="text"
                    placeholder="00:05:00"
                    className="w-full border border-gray-200 rounded-lg px-3 py-2"
                  />
                </div>
              </div>

              <div className="flex space-x-2">
                <Button variant="outline" className="flex-1">
                  <Play className="w-4 h-4 mr-2" />
                  Preview
                </Button>
                <Button className="flex-1">
                  <Scissors className="w-4 h-4 mr-2" />
                  Trim Audio
                </Button>
              </div>
            </CardContent>
          </Card>
        );

      case "monetize":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Skiza Tone Setup</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-green-50 p-4 rounded-lg">
                <h4 className="font-medium text-green-800 mb-2">
                  Skiza Tone Requirements
                </h4>
                <ul className="text-sm text-green-700 space-y-1">
                  <li>• Maximum duration: 30 seconds</li>
                  <li>• Format: MP3 or AAC</li>
                  <li>• Quality: 128 kbps minimum</li>
                  <li>• No explicit content</li>
                </ul>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Clip Duration (seconds)
                </label>
                <input
                  type="range"
                  min="5"
                  max="30"
                  defaultValue="20"
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>5s</span>
                  <span>20s</span>
                  <span>30s</span>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Title
                </label>
                <input
                  type="text"
                  placeholder="My Skiza Tone"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Category
                </label>
                <select className="w-full border border-gray-200 rounded-lg px-3 py-2">
                  <option>Music</option>
                  <option>Comedy</option>
                  <option>Sound Effects</option>
                  <option>Inspirational</option>
                  <option>Other</option>
                </select>
              </div>

              <Button className="w-full">
                <DollarSign className="w-4 h-4 mr-2" />
                Prepare for Skiza
              </Button>
            </CardContent>
          </Card>
        );

      case "enhance":
        return (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Audio Enhancement</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Noise Reduction
                  </label>
                  <input type="range" className="w-full" defaultValue="50" />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Bass Boost
                  </label>
                  <input type="range" className="w-full" defaultValue="30" />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Treble Enhancement
                  </label>
                  <input type="range" className="w-full" defaultValue="20" />
                </div>

                <div className="space-y-2">
                  <label className="flex items-center">
                    <input type="checkbox" className="rounded mr-2" />
                    <span className="text-sm">Auto-normalize volume</span>
                  </label>
                  <label className="flex items-center">
                    <input type="checkbox" className="rounded mr-2" />
                    <span className="text-sm">Remove background hum</span>
                  </label>
                  <label className="flex items-center">
                    <input type="checkbox" className="rounded mr-2" />
                    <span className="text-sm">Enhance speech clarity</span>
                  </label>
                </div>
              </div>

              <div className="flex space-x-2">
                <Button variant="outline" className="flex-1">
                  <Play className="w-4 h-4 mr-2" />
                  Preview
                </Button>
                <Button className="flex-1">
                  <Zap className="w-4 h-4 mr-2" />
                  Enhance
                </Button>
              </div>
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
        <Headphones className="w-12 h-12 mx-auto text-purple-600 mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Audio Tools
        </h3>
        <p className="text-sm text-gray-600">
          Professional audio editing and enhancement tools
        </p>
      </div>

      {/* Audio Player */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="font-medium">{file.name}</p>
              <p className="text-sm text-gray-500">
                {file.duration} • {file.size}
              </p>
            </div>
          </div>

          <div className="flex items-center justify-center space-x-4">
            <Button size="sm" variant="outline">
              <SkipBack className="w-4 h-4" />
            </Button>
            <Button
              size="sm"
              onClick={() => setIsPlaying(!isPlaying)}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {isPlaying ? (
                <Pause className="w-4 h-4" />
              ) : (
                <Play className="w-4 h-4" />
              )}
            </Button>
            <Button size="sm" variant="outline">
              <SkipForward className="w-4 h-4" />
            </Button>
          </div>

          {/* Progress bar placeholder */}
          <div className="mt-4 bg-gray-200 rounded-full h-2">
            <div className="bg-purple-600 h-2 rounded-full w-1/3"></div>
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
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <p className="text-sm text-gray-600">Processing your audio...</p>
        </div>
      )}

      {renderToolInterface()}
    </div>
  );
}
