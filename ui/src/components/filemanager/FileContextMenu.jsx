// components/FileManager/components/FileContextMenu.jsx
import React, { useEffect } from "react";
import {
  Eye,
  Download,
  Share2,
  Copy,
  Scissors,
  Trash2,
  Star,
  Edit3,
  Info,
  FolderPlus,
  Move,
  Settings,
} from "lucide-react";

export default function FileContextMenu({
  contextMenu,
  setContextMenu,
  onStarToggle,
  onCopy,
  onCut,
  onDelete,
  onShare,
  setSelectedItem,
  setShowRightPanel,
  setPanelType,
  clipboard,
  onPaste,
}) {
  useEffect(() => {
    const handleClickOutside = () => {
      setContextMenu({ show: false, x: 0, y: 0, targetFile: null });
    };

    const handleScroll = () => {
      setContextMenu({ show: false, x: 0, y: 0, targetFile: null });
    };

    if (contextMenu.show) {
      document.addEventListener("click", handleClickOutside);
      document.addEventListener("scroll", handleScroll, true);
    }

    return () => {
      document.removeEventListener("click", handleClickOutside);
      document.removeEventListener("scroll", handleScroll, true);
    };
  }, [contextMenu.show, setContextMenu]);

  if (!contextMenu.show || !contextMenu.targetFile) return null;

  const { targetFile } = contextMenu;

  const menuItems = [
    {
      icon: Eye,
      label: "View Details",
      action: () => {
        setSelectedItem(targetFile);
        setShowRightPanel(true);
        setPanelType("details");
      },
    },
    {
      icon: Settings,
      label: "Open Tools",
      action: () => {
        setSelectedItem(targetFile);
        setShowRightPanel(true);
        setPanelType("tools");
      },
      disabled: targetFile.type === "folder",
    },
    { separator: true },
    {
      icon: Download,
      label: "Download",
      action: () => console.log("Download file"),
      disabled: targetFile.type === "folder",
    },
    {
      icon: Share2,
      label: "Share",
      action: onShare,
    },
    { separator: true },
    {
      icon: Star,
      label: targetFile.starred ? "Remove Star" : "Add Star",
      action: () => onStarToggle(targetFile.id),
    },
    {
      icon: Edit3,
      label: "Rename",
      action: () => console.log("Rename file"),
    },
    { separator: true },
    {
      icon: Copy,
      label: "Copy",
      action: onCopy,
    },
    {
      icon: Scissors,
      label: "Cut",
      action: onCut,
    },
    {
      icon: Move,
      label: "Paste",
      action: onPaste,
      disabled: clipboard.files.length === 0,
    },
    { separator: true },
    {
      icon: FolderPlus,
      label: "New Folder Here",
      action: () => console.log("Create folder"),
      disabled: targetFile.type !== "folder",
    },
    { separator: true },
    {
      icon: Trash2,
      label: "Delete",
      action: onDelete,
      className: "text-red-600 hover:bg-red-50",
    },
  ];

  return (
    <div
      className="fixed bg-white border border-slate-200 rounded-lg shadow-xl py-2 z-50 min-w-[180px]"
      style={{
        left: Math.min(contextMenu.x, window.innerWidth - 200),
        top: Math.min(contextMenu.y, window.innerHeight - 400),
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {menuItems.map((item, index) => {
        if (item.separator) {
          return <div key={index} className="border-t border-slate-200 my-1" />;
        }

        if (item.disabled) {
          return (
            <div
              key={index}
              className="flex items-center px-4 py-2 text-sm text-slate-400 cursor-not-allowed"
            >
              <item.icon className="w-4 h-4 mr-3" />
              {item.label}
            </div>
          );
        }

        return (
          <button
            key={index}
            onClick={(e) => {
              e.stopPropagation();
              item.action();
              setContextMenu({ show: false, x: 0, y: 0, targetFile: null });
            }}
            className={`w-full flex items-center px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors ${
              item.className || ""
            }`}
          >
            <item.icon className="w-4 h-4 mr-3" />
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
