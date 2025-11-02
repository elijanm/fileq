// components/FileManager/components/FiltersPanel.jsx
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  X,
  Filter,
  FileType,
  Calendar,
  HardDrive,
  User,
  Star,
  Share2,
  Tag,
  Clock,
  RotateCcw,
  Search,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

export default function FiltersPanel({
  filterType,
  setFilterType,
  filterDate,
  setFilterDate,
  filterSize,
  setFilterSize,
  searchQuery,
  setSearchQuery,
  onClose,
}) {
  const [activeFilters, setActiveFilters] = useState({
    starred: false,
    shared: false,
    owned: false,
  });
  const [sizeRange, setSizeRange] = useState({ min: "", max: "" });
  const [dateRange, setDateRange] = useState({ start: "", end: "" });
  const [selectedTags, setSelectedTags] = useState([]);
  const [expandedSections, setExpandedSections] = useState(
    new Set(["type", "date", "size", "attributes"])
  );

  const toggleSection = (section) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(section)) {
      newExpanded.delete(section);
    } else {
      newExpanded.add(section);
    }
    setExpandedSections(newExpanded);
  };

  const fileTypes = [
    { id: "all", label: "All Files", icon: FileType, count: 0 },
    { id: "folder", label: "Folders", icon: FileType, count: 0 },
    { id: "pdf", label: "PDF Documents", icon: FileType, count: 0 },
    { id: "image", label: "Images", icon: FileType, count: 0 },
    { id: "video", label: "Videos", icon: FileType, count: 0 },
    { id: "audio", label: "Audio Files", icon: FileType, count: 0 },
    { id: "document", label: "Documents", icon: FileType, count: 0 },
    { id: "presentation", label: "Presentations", icon: FileType, count: 0 },
    { id: "spreadsheet", label: "Spreadsheets", icon: FileType, count: 0 },
    { id: "archive", label: "Archives", icon: FileType, count: 0 },
    { id: "code", label: "Code Files", icon: FileType, count: 0 },
  ];

  const dateOptions = [
    { id: "all", label: "All Time" },
    { id: "today", label: "Today" },
    { id: "yesterday", label: "Yesterday" },
    { id: "week", label: "This Week" },
    { id: "month", label: "This Month" },
    { id: "quarter", label: "This Quarter" },
    { id: "year", label: "This Year" },
    { id: "custom", label: "Custom Range" },
  ];

  const sizeOptions = [
    { id: "all", label: "All Sizes" },
    { id: "tiny", label: "Tiny (< 1 KB)" },
    { id: "small", label: "Small (< 1 MB)" },
    { id: "medium", label: "Medium (1MB - 100MB)" },
    { id: "large", label: "Large (100MB - 1GB)" },
    { id: "huge", label: "Huge (> 1GB)" },
    { id: "custom", label: "Custom Range" },
  ];

  const commonTags = [
    "work",
    "personal",
    "project",
    "important",
    "draft",
    "final",
    "review",
    "archive",
    "backup",
    "temp",
    "design",
    "development",
  ];

  const handleTagToggle = (tag) => {
    const newTags = selectedTags.includes(tag)
      ? selectedTags.filter((t) => t !== tag)
      : [...selectedTags, tag];
    setSelectedTags(newTags);
  };

  const handleActiveFilterToggle = (filterName) => {
    setActiveFilters({
      ...activeFilters,
      [filterName]: !activeFilters[filterName],
    });
  };

  const clearAllFilters = () => {
    setFilterType("all");
    setFilterDate("all");
    setFilterSize("all");
    setSearchQuery("");
    setActiveFilters({ starred: false, shared: false, owned: false });
    setSizeRange({ min: "", max: "" });
    setDateRange({ start: "", end: "" });
    setSelectedTags([]);
  };

  const getActiveFiltersCount = () => {
    let count = 0;
    if (filterType !== "all") count++;
    if (filterDate !== "all") count++;
    if (filterSize !== "all") count++;
    if (searchQuery) count++;
    if (Object.values(activeFilters).some((v) => v)) count++;
    if (selectedTags.length > 0) count++;
    return count;
  };

  const FilterSection = ({ id, title, icon: Icon, children }) => {
    const isExpanded = expandedSections.has(id);

    return (
      <div className="border border-slate-200 rounded-lg">
        <button
          onClick={() => toggleSection(id)}
          className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
        >
          <div className="flex items-center space-x-2">
            <Icon className="w-4 h-4 text-slate-600" />
            <span className="font-medium text-slate-900">{title}</span>
          </div>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </button>
        {isExpanded && (
          <div className="border-t border-slate-200 p-4">{children}</div>
        )}
      </div>
    );
  };

  return (
    <Card className="border-0 shadow-lg">
      <CardHeader className="border-b border-slate-200">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center text-lg">
            <Filter className="w-5 h-5 mr-2 text-blue-600" />
            Filters
            {getActiveFiltersCount() > 0 && (
              <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full">
                {getActiveFiltersCount()}
              </span>
            )}
          </CardTitle>
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="w-4 h-4" />
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-4 space-y-4 max-h-[70vh] overflow-y-auto">
        {/* Search Filter */}
        <FilterSection id="search" title="Search" icon={Search}>
          <div className="space-y-3">
            <input
              type="text"
              placeholder="Search files and folders..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <div className="text-xs text-slate-500">
              Search in file names, descriptions, and content
            </div>
          </div>
        </FilterSection>

        {/* File Type Filter */}
        <FilterSection id="type" title="File Type" icon={FileType}>
          <div className="space-y-2">
            {fileTypes.map((type) => (
              <label key={type.id} className="flex items-center cursor-pointer">
                <input
                  type="radio"
                  name="fileType"
                  value={type.id}
                  checked={filterType === type.id}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="mr-3 text-blue-600"
                />
                <span className="text-sm text-slate-700 flex-1">
                  {type.label}
                </span>
                {type.count > 0 && (
                  <span className="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded">
                    {type.count}
                  </span>
                )}
              </label>
            ))}
          </div>
        </FilterSection>

        {/* Date Filter */}
        <FilterSection id="date" title="Date Modified" icon={Calendar}>
          <div className="space-y-3">
            <div className="space-y-2">
              {dateOptions.map((option) => (
                <label
                  key={option.id}
                  className="flex items-center cursor-pointer"
                >
                  <input
                    type="radio"
                    name="dateFilter"
                    value={option.id}
                    checked={filterDate === option.id}
                    onChange={(e) => setFilterDate(e.target.value)}
                    className="mr-3 text-blue-600"
                  />
                  <span className="text-sm text-slate-700">{option.label}</span>
                </label>
              ))}
            </div>

            {filterDate === "custom" && (
              <div className="grid grid-cols-2 gap-3 mt-3 pt-3 border-t">
                <div>
                  <label className="block text-xs text-slate-600 mb-1">
                    From
                  </label>
                  <input
                    type="date"
                    value={dateRange.start}
                    onChange={(e) =>
                      setDateRange({ ...dateRange, start: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded px-2 py-1 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">
                    To
                  </label>
                  <input
                    type="date"
                    value={dateRange.end}
                    onChange={(e) =>
                      setDateRange({ ...dateRange, end: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded px-2 py-1 text-sm"
                  />
                </div>
              </div>
            )}
          </div>
        </FilterSection>

        {/* Size Filter */}
        <FilterSection id="size" title="File Size" icon={HardDrive}>
          <div className="space-y-3">
            <div className="space-y-2">
              {sizeOptions.map((option) => (
                <label
                  key={option.id}
                  className="flex items-center cursor-pointer"
                >
                  <input
                    type="radio"
                    name="sizeFilter"
                    value={option.id}
                    checked={filterSize === option.id}
                    onChange={(e) => setFilterSize(e.target.value)}
                    className="mr-3 text-blue-600"
                  />
                  <span className="text-sm text-slate-700">{option.label}</span>
                </label>
              ))}
            </div>

            {filterSize === "custom" && (
              <div className="grid grid-cols-2 gap-3 mt-3 pt-3 border-t">
                <div>
                  <label className="block text-xs text-slate-600 mb-1">
                    Min Size
                  </label>
                  <input
                    type="text"
                    placeholder="e.g., 1MB"
                    value={sizeRange.min}
                    onChange={(e) =>
                      setSizeRange({ ...sizeRange, min: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded px-2 py-1 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">
                    Max Size
                  </label>
                  <input
                    type="text"
                    placeholder="e.g., 100MB"
                    value={sizeRange.max}
                    onChange={(e) =>
                      setSizeRange({ ...sizeRange, max: e.target.value })
                    }
                    className="w-full border border-slate-200 rounded px-2 py-1 text-sm"
                  />
                </div>
              </div>
            )}
          </div>
        </FilterSection>

        {/* Attributes Filter */}
        <FilterSection id="attributes" title="Attributes" icon={Star}>
          <div className="space-y-3">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={activeFilters.starred}
                onChange={() => handleActiveFilterToggle("starred")}
                className="mr-3 rounded text-blue-600"
              />
              <Star className="w-4 h-4 mr-2 text-yellow-500" />
              <span className="text-sm text-slate-700">Starred files</span>
            </label>

            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={activeFilters.shared}
                onChange={() => handleActiveFilterToggle("shared")}
                className="mr-3 rounded text-blue-600"
              />
              <Share2 className="w-4 h-4 mr-2 text-green-500" />
              <span className="text-sm text-slate-700">Shared files</span>
            </label>

            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={activeFilters.owned}
                onChange={() => handleActiveFilterToggle("owned")}
                className="mr-3 rounded text-blue-600"
              />
              <User className="w-4 h-4 mr-2 text-blue-500" />
              <span className="text-sm text-slate-700">Owned by me</span>
            </label>
          </div>
        </FilterSection>

        {/* Tags Filter */}
        <FilterSection id="tags" title="Tags" icon={Tag}>
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {commonTags.map((tag) => (
                <button
                  key={tag}
                  onClick={() => handleTagToggle(tag)}
                  className={`px-2 py-1 text-xs rounded-full border transition-colors ${
                    selectedTags.includes(tag)
                      ? "bg-blue-100 text-blue-700 border-blue-200"
                      : "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  {tag}
                </button>
              ))}
            </div>

            {selectedTags.length > 0 && (
              <div className="pt-2 border-t">
                <div className="text-xs text-slate-600 mb-2">
                  Selected tags:
                </div>
                <div className="flex flex-wrap gap-1">
                  {selectedTags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded"
                    >
                      {tag}
                      <button
                        onClick={() => handleTagToggle(tag)}
                        className="ml-1 hover:text-blue-900"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </FilterSection>

        {/* Quick Actions */}
        <div className="pt-4 border-t border-slate-200">
          <div className="flex space-x-2">
            <Button
              variant="outline"
              onClick={clearAllFilters}
              className="flex-1"
              disabled={getActiveFiltersCount() === 0}
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Clear All
            </Button>
            {onClose && (
              <Button
                onClick={onClose}
                className="flex-1 bg-blue-600 hover:bg-blue-700"
              >
                Apply Filters
              </Button>
            )}
          </div>
        </div>

        {/* Active Filters Summary */}
        {getActiveFiltersCount() > 0 && (
          <div className="bg-blue-50 p-3 rounded-lg">
            <div className="text-sm font-medium text-blue-800 mb-2">
              Active Filters ({getActiveFiltersCount()})
            </div>
            <div className="space-y-1 text-xs text-blue-700">
              {filterType !== "all" && (
                <div>
                  File Type: {fileTypes.find((t) => t.id === filterType)?.label}
                </div>
              )}
              {filterDate !== "all" && (
                <div>
                  Date: {dateOptions.find((d) => d.id === filterDate)?.label}
                </div>
              )}
              {filterSize !== "all" && (
                <div>
                  Size: {sizeOptions.find((s) => s.id === filterSize)?.label}
                </div>
              )}
              {searchQuery && <div>Search: "{searchQuery}"</div>}
              {Object.entries(activeFilters)
                .filter(([_, active]) => active)
                .map(([filter]) => (
                  <div key={filter}>
                    {filter === "starred" && "Starred files only"}
                    {filter === "shared" && "Shared files only"}
                    {filter === "owned" && "Owned by me only"}
                  </div>
                ))}
              {selectedTags.length > 0 && (
                <div>Tags: {selectedTags.join(", ")}</div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
