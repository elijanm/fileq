import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import FileQLanding from "@/pages/LandingPage";
import ToolPage from "@/pages/ToolPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<FileQLanding />} />
      <Route path="/tools/:toolId" element={<ToolPage />} />
      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
