// components/ToolsGrid.jsx
import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
    Share2, Download, Lock, Merge, Scissors, Archive,
    Maximize, Crop, Sparkles, RefreshCw, FileText,
    VolumeX, Subtitles, FileType
} from "lucide-react";

export default function ToolsGrid({ fileInfo, onToolClick }) {
    // Common tools that appear for all file types
    const commonTools = [
        {
            id: "share",
            name: "Share",
            description: "Share file with others",
            icon: Share2,
            color: "bg-blue-50 hover:bg-blue-100 border-blue-200",
            iconColor: "text-blue-600",
            category: "common"
        },
        {
            id: "download",
            name: "Download",
            description: "Download your file",
            icon: Download,
            color: "bg-green-50 hover:bg-green-100 border-green-200",
            iconColor: "text-green-600",
            category: "common"
        },
        {
            id: "encrypt",
            name: "Encrypt",
            description: "Password protect file",
            icon: Lock,
            color: "bg-slate-50 hover:bg-slate-100 border-slate-200",
            iconColor: "text-slate-600",
            category: "common"
        }
    ];

    // File type specific tools
    const fileTypeTools = {
        pdf: [
            {
                id: "pdf-merge",
                name: "Merge PDFs",
                description: "Combine multiple PDFs",
                icon: Merge,
                color: "bg-red-50 hover:bg-red-100 border-red-200",
                iconColor: "text-red-600"
            },
            {
                id: "pdf-split",
                name: "Split PDF",
                description: "Extract pages",
                icon: Scissors,
                color: "bg-red-50 hover:bg-red-100 border-red-200",
                iconColor: "text-red-600"
            },
            {
                id: "pdf-compress",
                name: "Compress PDF",
                description: "Reduce file size",
                icon: Archive,
                color: "bg-red-50 hover:bg-red-100 border-red-200",
                iconColor: "text-red-600"
            }
        ],
        image: [
            {
                id: "image-resize",
                name: "Resize",
                description: "Change dimensions",
                icon: Maximize,
                color: "bg-purple-50 hover:bg-purple-100 border-purple-200",
                iconColor: "text-purple-600"
            },
            {
                id: "image-crop",
                name: "Crop",
                description: "Trim image edges",
                icon: Crop,
                color: "bg-purple-50 hover:bg-purple-100 border-purple-200",
                iconColor: "text-purple-600"
            },
            {
                id: "image-enhance",
                name: "Enhance",
                description: "AI-powered improvement",
                icon: Sparkles,
                color: "bg-purple-50 hover:bg-purple-100 border-purple-200",
                iconColor: "text-purple-600"
            },
            {
                id: "image-convert",
                name: "Convert Format",
                description: "Change file type",
                icon: RefreshCw,
                color: "bg-purple-50 hover:bg-purple-100 border-purple-200",
                iconColor: "text-purple-600"
            }
        ],
        audio: [
            {
                id: "audio-transcribe",
                name: "Transcribe",
                description: "Speech to text",
                icon: FileText,
                color: "bg-green-50 hover:bg-green-100 border-green-200",
                iconColor: "text-green-600"
            },
            {
                id: "audio-trim",
                name: "Trim Audio",
                description: "Cut audio segments",
                icon: Scissors,
                color: "bg-green-50 hover:bg-green-100 border-green-200",
                iconColor: "text-green-600"
            },
            {
                id: "audio-convert",
                name: "Convert Audio",
                description: "Change format",
                icon: RefreshCw,
                color: "bg-green-50 hover:bg-green-100 border-green-200",
                iconColor: "text-green-600"
            }
        ],
        video: [
            {
                id: "video-subtitles",
                name: "Add Subtitles",
                description: "Generate captions",
                icon: Subtitles,
                color: "bg-orange-50 hover:bg-orange-100 border-orange-200",
                iconColor: "text-orange-600"
            },
            {
                id: "video-trim",
                name: "Trim Video",
                description: "Cut video segments",
                icon: Scissors,
                color: "bg-orange-50 hover:bg-orange-100 border-orange-200",
                iconColor: "text-orange-600"
            },
            {
                id: "video-extract-audio",
                name: "Extract Audio",
                description: "Get audio track",
                icon: VolumeX,
                color: "bg-orange-50 hover:bg-orange-100 border-orange-200",
                iconColor: "text-orange-600"
            }
        ]
    };

    const getFileTypeCategory = (mimeType) => {
        if (!mimeType) return "unknown";
        if (mimeType.includes("pdf")) return "pdf";
        if (mimeType.startsWith("image/")) return "image";
        if (mimeType.startsWith("audio/")) return "audio";
        if (mimeType.startsWith("video/")) return "video";
        return "document";
    };

    const getAvailableTools = (mimeType) => {
        const category = getFileTypeCategory(mimeType);
        const specificTools = fileTypeTools[category] || [];
        return [...commonTools, ...specificTools];
    };

    const tools = getAvailableTools(fileInfo?.type);

    return (
        <div className="space-y-6 animate-in slide-in-from-right-5 duration-500">
            <div>
                <h2 className="text-3xl font-bold text-slate-900 mb-2">Available Tools</h2>
                <p className="text-lg text-slate-600">
                    Tools for your {getFileTypeCategory(fileInfo?.type)} file
                </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {tools.map((tool) => {
                    const IconComponent = tool.icon;
                    return (
                        <Card
                            key={tool.id}
                            className={`cursor-pointer transition-all duration-200 hover:shadow-lg hover:scale-105 ${tool.color} border-2`}
                            onClick={() => onToolClick(tool.id)}
                        >
                            <CardContent className="p-6">
                                <div className="text-center space-y-3">
                                    <div className="w-12 h-12 rounded-xl bg-white shadow-sm flex items-center justify-center mx-auto">
                                        <IconComponent className={`w-6 h-6 ${tool.iconColor}`} />
                                    </div>
                                    <div>
                                        <h3 className="font-semibold text-slate-900">{tool.name}</h3>
                                        <p className="text-sm text-slate-600">{tool.description}</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    );
                })}
            </div>

            {tools.length === 0 && (
                <Card className="border-2 border-slate-200 bg-slate-50">
                    <CardContent className="p-8 text-center">
                        <FileType className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                        <h3 className="text-lg font-semibold text-slate-900 mb-2">General Tools Available</h3>
                        <p className="text-slate-600">
                            While we don't have specialized tools for this file type, you can still use our security and conversion tools.
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}