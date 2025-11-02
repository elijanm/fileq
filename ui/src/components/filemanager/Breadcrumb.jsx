// components/FileManager/components/Breadcrumb.jsx
import React from "react";
import { ChevronRight, Home } from "lucide-react";

export default function Breadcrumb({ currentFolder, setCurrentFolder }) {
  const pathParts = currentFolder.split("/").filter(Boolean);

  const navigateToPath = (index) => {
    if (index === -1) {
      setCurrentFolder("/");
    } else {
      const newPath = "/" + pathParts.slice(0, index + 1).join("/");
      setCurrentFolder(newPath);
    }
  };

  return (
    <nav className="flex items-center space-x-2 text-sm">
      <button
        onClick={() => navigateToPath(-1)}
        className="flex items-center text-blue-600 hover:text-blue-700 font-medium transition-colors"
      >
        <Home className="w-4 h-4 mr-1" />
        Home
      </button>

      {pathParts.map((part, index) => (
        <React.Fragment key={index}>
          <ChevronRight className="w-4 h-4 text-slate-400" />
          <button
            onClick={() => navigateToPath(index)}
            className="text-blue-600 hover:text-blue-700 font-medium transition-colors"
          >
            {part}
          </button>
        </React.Fragment>
      ))}
    </nav>
  );
}
