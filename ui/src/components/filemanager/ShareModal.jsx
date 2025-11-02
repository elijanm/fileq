// components/FileManager/components/ShareModal.jsx
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  X,
  Link,
  Mail,
  MessageCircle,
  Send,
  Copy,
  Users,
  Globe,
  Lock,
  Eye,
  Edit3,
  Calendar,
  Settings,
  ExternalLink,
} from "lucide-react";

export default function ShareModal({ isOpen, onClose, selectedItem }) {
  const [shareMethod, setShareMethod] = useState("link");
  const [permissions, setPermissions] = useState("view");
  const [expiryDate, setExpiryDate] = useState("");
  const [password, setPassword] = useState("");
  const [emailList, setEmailList] = useState("");
  const [message, setMessage] = useState("");
  const [linkCopied, setLinkCopied] = useState(false);

  if (!isOpen || !selectedItem) return null;

  const shareUrl = `https://filemanager.app/share/${selectedItem.id}`;

  const handleCopyLink = () => {
    navigator.clipboard.writeText(shareUrl);
    setLinkCopied(true);
    setTimeout(() => setLinkCopied(false), 2000);
  };

  const shareMethods = [
    {
      id: "link",
      name: "Share Link",
      description: "Generate a shareable link",
      icon: Link,
      color: "text-blue-600",
      bgColor: "bg-blue-50",
    },
    {
      id: "email",
      name: "Email",
      description: "Send via email",
      icon: Mail,
      color: "text-green-600",
      bgColor: "bg-green-50",
    },
    {
      id: "whatsapp",
      name: "WhatsApp",
      description: "Share on WhatsApp",
      icon: MessageCircle,
      color: "text-emerald-600",
      bgColor: "bg-emerald-50",
    },
    {
      id: "telegram",
      name: "Telegram",
      description: "Share on Telegram",
      icon: Send,
      color: "text-blue-500",
      bgColor: "bg-blue-50",
    },
  ];

  const permissionOptions = [
    {
      id: "view",
      name: "View Only",
      description: "Can view and download",
      icon: Eye,
    },
    {
      id: "comment",
      name: "Comment",
      description: "Can view and comment",
      icon: MessageCircle,
    },
    {
      id: "edit",
      name: "Edit",
      description: "Can view, comment, and edit",
      icon: Edit3,
    },
  ];

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader className="border-b">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center">
              <Users className="w-5 h-5 mr-2 text-blue-600" />
              Share "{selectedItem.name}"
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="w-4 h-4" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-6 space-y-6">
          {/* Share Method Selection */}
          <div>
            <h3 className="text-sm font-medium text-gray-900 mb-3">
              Share Method
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {shareMethods.map((method) => {
                const Icon = method.icon;
                return (
                  <Card
                    key={method.id}
                    className={`cursor-pointer transition-all ${
                      shareMethod === method.id
                        ? "ring-2 ring-blue-500 shadow-md"
                        : "hover:shadow-md"
                    }`}
                    onClick={() => setShareMethod(method.id)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center space-x-3">
                        <div className={`p-2 rounded-lg ${method.bgColor}`}>
                          <Icon className={`w-5 h-5 ${method.color}`} />
                        </div>
                        <div className="flex-1">
                          <h4 className="font-medium text-gray-900">
                            {method.name}
                          </h4>
                          <p className="text-sm text-gray-600">
                            {method.description}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>

          {/* Permissions */}
          <div>
            <h3 className="text-sm font-medium text-gray-900 mb-3">
              Permissions
            </h3>
            <div className="space-y-2">
              {permissionOptions.map((option) => {
                const Icon = option.icon;
                return (
                  <label
                    key={option.id}
                    className="flex items-center p-3 border rounded-lg cursor-pointer hover:bg-gray-50"
                  >
                    <input
                      type="radio"
                      name="permissions"
                      value={option.id}
                      checked={permissions === option.id}
                      onChange={() => setPermissions(option.id)}
                      className="mr-3"
                    />
                    <Icon className="w-5 h-5 text-gray-600 mr-3" />
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">
                        {option.name}
                      </div>
                      <div className="text-sm text-gray-600">
                        {option.description}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Advanced Settings */}
          <div className="border-t pt-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-gray-900">
                Advanced Settings
              </h3>
              <Settings className="w-4 h-4 text-gray-400" />
            </div>

            <div className="space-y-4">
              {/* Expiry Date */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Link Expiry (Optional)
                </label>
                <div className="flex items-center space-x-2">
                  <Calendar className="w-4 h-4 text-gray-400" />
                  <input
                    type="date"
                    value={expiryDate}
                    onChange={(e) => setExpiryDate(e.target.value)}
                    className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>

              {/* Password Protection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Password Protection (Optional)
                </label>
                <div className="flex items-center space-x-2">
                  <Lock className="w-4 h-4 text-gray-400" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password"
                    className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>

              {/* Public Link Toggle */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Globe className="w-4 h-4 text-gray-400" />
                  <span className="text-sm font-medium text-gray-700">
                    Allow public access
                  </span>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" className="sr-only peer" />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
            </div>
          </div>

          {/* Share Interface */}
          {shareMethod === "link" && (
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-700">
                  Share Link
                </span>
                <Button
                  size="sm"
                  onClick={handleCopyLink}
                  className={linkCopied ? "bg-green-600" : ""}
                >
                  <Copy className="w-4 h-4 mr-2" />
                  {linkCopied ? "Copied!" : "Copy"}
                </Button>
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  value={shareUrl}
                  readOnly
                  className="flex-1 bg-white border border-gray-200 rounded px-3 py-2 text-sm"
                />
                <Button size="sm" variant="outline">
                  <ExternalLink className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}

          {shareMethod === "email" && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Email Recipients (comma-separated)
                </label>
                <textarea
                  value={emailList}
                  onChange={(e) => setEmailList(e.target.value)}
                  placeholder="john@example.com, jane@example.com"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm h-20 resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Message (Optional)
                </label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Add a personal message..."
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm h-24 resize-none"
                />
              </div>
            </div>
          )}

          {(shareMethod === "whatsapp" || shareMethod === "telegram") && (
            <div className="bg-gray-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600 mb-3">
                Click the button below to share via{" "}
                {shareMethod === "whatsapp" ? "WhatsApp" : "Telegram"}
              </p>
              <div className="text-sm bg-white p-3 rounded border">
                <strong>📁 {selectedItem.name}</strong>
                <br />
                Check out this{" "}
                {selectedItem.type === "folder" ? "folder" : "file"}: {shareUrl}
                {message && (
                  <>
                    <br />
                    <br />
                    {message}
                  </>
                )}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex justify-end space-x-3 pt-4 border-t">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                // Handle share action based on method
                if (shareMethod === "email") {
                  console.log("Sending email to:", emailList);
                } else if (shareMethod === "whatsapp") {
                  const text = encodeURIComponent(
                    `📁 ${selectedItem.name}\nCheck out this ${
                      selectedItem.type === "folder" ? "folder" : "file"
                    }: ${shareUrl}${message ? `\n\n${message}` : ""}`
                  );
                  window.open(`https://wa.me/?text=${text}`, "_blank");
                } else if (shareMethod === "telegram") {
                  const text = encodeURIComponent(
                    `📁 ${selectedItem.name}\nCheck out this ${
                      selectedItem.type === "folder" ? "folder" : "file"
                    }: ${shareUrl}${message ? `\n\n${message}` : ""}`
                  );
                  window.open(
                    `https://t.me/share/url?url=${shareUrl}&text=${text}`,
                    "_blank"
                  );
                }
                onClose();
              }}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {shareMethod === "link"
                ? "Generate Link"
                : shareMethod === "email"
                ? "Send Email"
                : `Share via ${
                    shareMethod === "whatsapp" ? "WhatsApp" : "Telegram"
                  }`}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
