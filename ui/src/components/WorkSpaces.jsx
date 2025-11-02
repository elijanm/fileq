import React, { useState } from "react";
import {
  Users,
  Building,
  Plus,
  UserPlus,
  Send,
  Settings,
  Crown,
  X,
  Check,
  Mail,
  Copy,
  ExternalLink,
  Trash2,
  Edit,
  MoreHorizontal,
  Folder,
  Files,
  Calendar,
  Activity,
} from "lucide-react";

export default function WorkSpaces() {
  const [activeTab, setActiveTab] = useState("teams");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState(null);

  // Button component
  const Button = ({
    children,
    onClick,
    variant = "default",
    size = "default",
    className,
    disabled,
    ...props
  }) => {
    const baseClasses =
      "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
    const variants = {
      default: "bg-blue-600 text-white hover:bg-blue-700",
      outline:
        "border border-slate-200 bg-white hover:bg-slate-100 hover:text-slate-900",
      ghost: "hover:bg-slate-100",
      destructive: "bg-red-600 text-white hover:bg-red-700",
    };
    const sizes = {
      default: "h-10 py-2 px-4",
      sm: "h-9 px-3 text-sm",
      lg: "h-11 px-8",
    };

    return (
      <button
        className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${
          className || ""
        }`}
        onClick={onClick}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    );
  };

  // Card component
  const Card = ({ children, className }) => (
    <div
      className={`bg-white rounded-lg shadow border border-slate-200 ${
        className || ""
      }`}
    >
      {children}
    </div>
  );

  const CardHeader = ({ children, className }) => (
    <div className={`px-6 py-4 border-b border-slate-200 ${className || ""}`}>
      {children}
    </div>
  );

  const CardTitle = ({ children, className }) => (
    <h3 className={`text-lg font-semibold ${className || ""}`}>{children}</h3>
  );

  const CardContent = ({ children, className }) => (
    <div className={`p-6 ${className || ""}`}>{children}</div>
  );

  const teams = [
    {
      id: 1,
      name: "Marketing Team",
      description: "Brand assets, campaigns, and marketing materials",
      members: 8,
      files: 156,
      storage: "2.4 GB",
      lastActivity: "2 hours ago",
      color: "blue",
      role: "Owner",
    },
    {
      id: 2,
      name: "Product Development",
      description: "Product specs, designs, and development resources",
      members: 12,
      files: 289,
      storage: "4.1 GB",
      lastActivity: "30 minutes ago",
      color: "green",
      role: "Admin",
    },
    {
      id: 3,
      name: "Sales Team",
      description: "Sales materials, presentations, and client files",
      members: 6,
      files: 94,
      storage: "1.2 GB",
      lastActivity: "1 day ago",
      color: "purple",
      role: "Member",
    },
  ];

  const spaces = [
    {
      id: 1,
      name: "Q1 2025 Campaign",
      team: "Marketing Team",
      files: 45,
      size: "890 MB",
      lastModified: "2 hours ago",
      type: "project",
    },
    {
      id: 2,
      name: "Brand Assets",
      team: "Marketing Team",
      files: 78,
      size: "1.2 GB",
      lastModified: "1 day ago",
      type: "shared",
    },
    {
      id: 3,
      name: "Mobile App Redesign",
      team: "Product Development",
      files: 156,
      size: "2.8 GB",
      lastModified: "5 hours ago",
      type: "project",
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <main className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">
              Teams & Spaces
            </h1>
            <p className="text-slate-600 mt-1">
              Collaborate and organize files with your team
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <Button onClick={() => setShowInviteModal(true)} variant="outline">
              <UserPlus className="w-4 h-4 mr-2" />
              Invite Members
            </Button>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Create Team
            </Button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex space-x-1 bg-slate-100 rounded-lg p-1 mb-8 w-fit">
          <button
            onClick={() => setActiveTab("teams")}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
              activeTab === "teams"
                ? "bg-white text-slate-900 shadow"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Users className="w-4 h-4 mr-2 inline" />
            Teams
          </button>
          <button
            onClick={() => setActiveTab("spaces")}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
              activeTab === "spaces"
                ? "bg-white text-slate-900 shadow"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Folder className="w-4 h-4 mr-2 inline" />
            Spaces
          </button>
        </div>

        {/* Teams Tab */}
        {activeTab === "teams" && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {teams.map((team) => (
              <Card
                key={team.id}
                className="hover:shadow-lg transition-shadow cursor-pointer group"
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div
                      className={`w-12 h-12 bg-${team.color}-100 rounded-lg flex items-center justify-center`}
                    >
                      <Building className={`w-6 h-6 text-${team.color}-600`} />
                    </div>
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button variant="ghost" size="sm">
                        <MoreHorizontal className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>

                  <h3 className="text-lg font-semibold text-slate-900 mb-2">
                    {team.name}
                  </h3>
                  <p className="text-sm text-slate-600 mb-4">
                    {team.description}
                  </p>

                  <div className="space-y-3 mb-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-500">Members</span>
                      <span className="font-medium text-slate-900">
                        {team.members}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-500">Files</span>
                      <span className="font-medium text-slate-900">
                        {team.files}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-500">Storage</span>
                      <span className="font-medium text-slate-900">
                        {team.storage}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                    <div className="flex items-center space-x-2">
                      <div
                        className={`px-2 py-1 rounded-full text-xs font-medium ${
                          team.role === "Owner"
                            ? "bg-yellow-100 text-yellow-800"
                            : team.role === "Admin"
                            ? "bg-blue-100 text-blue-800"
                            : "bg-slate-100 text-slate-800"
                        }`}
                      >
                        {team.role}
                      </div>
                    </div>
                    <span className="text-xs text-slate-500">
                      {team.lastActivity}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Spaces Tab */}
        {activeTab === "spaces" && (
          <div className="space-y-6">
            {/* Quick Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <Card>
                <CardContent className="p-6 text-center">
                  <Folder className="w-8 h-8 text-blue-600 mx-auto mb-2" />
                  <div className="text-2xl font-bold text-slate-900">
                    {spaces.length}
                  </div>
                  <div className="text-sm text-slate-600">Active Spaces</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6 text-center">
                  <Files className="w-8 h-8 text-green-600 mx-auto mb-2" />
                  <div className="text-2xl font-bold text-slate-900">
                    {spaces.reduce((acc, space) => acc + space.files, 0)}
                  </div>
                  <div className="text-sm text-slate-600">Total Files</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6 text-center">
                  <Activity className="w-8 h-8 text-purple-600 mx-auto mb-2" />
                  <div className="text-2xl font-bold text-slate-900">
                    {teams.length}
                  </div>
                  <div className="text-sm text-slate-600">Teams</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6 text-center">
                  <Users className="w-8 h-8 text-orange-600 mx-auto mb-2" />
                  <div className="text-2xl font-bold text-slate-900">
                    {teams.reduce((acc, team) => acc + team.members, 0)}
                  </div>
                  <div className="text-sm text-slate-600">Team Members</div>
                </CardContent>
              </Card>
            </div>

            {/* Spaces List */}
            <Card>
              <CardHeader>
                <CardTitle>Shared Spaces</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-slate-200">
                  {spaces.map((space) => (
                    <div
                      key={space.id}
                      className="p-6 hover:bg-slate-50 transition-colors cursor-pointer group"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                          <div
                            className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                              space.type === "project"
                                ? "bg-blue-100"
                                : "bg-green-100"
                            }`}
                          >
                            <Folder
                              className={`w-5 h-5 ${
                                space.type === "project"
                                  ? "text-blue-600"
                                  : "text-green-600"
                              }`}
                            />
                          </div>
                          <div>
                            <h4 className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">
                              {space.name}
                            </h4>
                            <div className="flex items-center space-x-4 text-sm text-slate-500">
                              <span>{space.team}</span>
                              <span>•</span>
                              <span>{space.files} files</span>
                              <span>•</span>
                              <span>{space.size}</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center space-x-4">
                          <span className="text-sm text-slate-500">
                            {space.lastModified}
                          </span>
                          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex space-x-1">
                            <Button variant="ghost" size="sm">
                              <ExternalLink className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="sm">
                              <MoreHorizontal className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Create Team Modal */}
        {showCreateModal && (
          <CreateTeamModal onClose={() => setShowCreateModal(false)} />
        )}

        {/* Invite Members Modal */}
        {showInviteModal && (
          <InviteMembersModal
            onClose={() => setShowInviteModal(false)}
            teams={teams}
          />
        )}
      </main>
    </div>
  );
}

// Create Team Modal
function CreateTeamModal({ onClose }) {
  const [teamName, setTeamName] = useState("");
  const [description, setDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Button component
  const Button = ({
    children,
    onClick,
    variant = "default",
    size = "default",
    className,
    disabled,
    ...props
  }) => {
    const baseClasses =
      "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
    const variants = {
      default: "bg-blue-600 text-white hover:bg-blue-700",
      outline:
        "border border-slate-200 bg-white hover:bg-slate-100 hover:text-slate-900",
      ghost: "hover:bg-slate-100",
    };
    const sizes = {
      default: "h-10 py-2 px-4",
      sm: "h-9 px-3 text-sm",
    };

    return (
      <button
        className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${
          className || ""
        }`}
        onClick={onClick}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    );
  };

  const handleCreate = async () => {
    setIsCreating(true);
    // Simulate API call
    setTimeout(() => {
      setIsCreating(false);
      onClose();
      alert("Team created successfully!");
    }, 1500);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
        <div className="flex items-center justify-between p-6 border-b border-slate-200">
          <h2 className="text-xl font-semibold text-slate-900">
            Create New Team
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Team Name
            </label>
            <input
              type="text"
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Enter team name"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full border border-slate-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="What's this team for?"
            />
          </div>
        </div>

        <div className="flex items-center justify-end space-x-3 p-6 border-t border-slate-200">
          <Button onClick={onClose} variant="outline">
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!teamName.trim() || isCreating}
          >
            {isCreating ? "Creating..." : "Create Team"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// Invite Members Modal
function InviteMembersModal({ onClose, teams }) {
  const [email, setEmail] = useState("");
  const [selectedTeam, setSelectedTeam] = useState(teams[0]?.id || "");
  const [role, setRole] = useState("member");
  const [invitedEmails, setInvitedEmails] = useState([]);
  const [isSending, setIsSending] = useState(false);

  // Button component
  const Button = ({
    children,
    onClick,
    variant = "default",
    size = "default",
    className,
    disabled,
    ...props
  }) => {
    const baseClasses =
      "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
    const variants = {
      default: "bg-blue-600 text-white hover:bg-blue-700",
      outline:
        "border border-slate-200 bg-white hover:bg-slate-100 hover:text-slate-900",
      ghost: "hover:bg-slate-100",
    };
    const sizes = {
      default: "h-10 py-2 px-4",
      sm: "h-9 px-3 text-sm",
    };

    return (
      <button
        className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${
          className || ""
        }`}
        onClick={onClick}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    );
  };

  const addEmail = () => {
    if (email && !invitedEmails.includes(email)) {
      setInvitedEmails([...invitedEmails, email]);
      setEmail("");
    }
  };

  const removeEmail = (emailToRemove) => {
    setInvitedEmails(invitedEmails.filter((e) => e !== emailToRemove));
  };

  const handleSendInvites = async () => {
    if (invitedEmails.length === 0) return;

    setIsSending(true);
    // Simulate API call
    setTimeout(() => {
      setIsSending(false);
      onClose();
      alert(`Invitations sent to ${invitedEmails.length} people!`);
    }, 1500);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4">
        <div className="flex items-center justify-between p-6 border-b border-slate-200">
          <h2 className="text-xl font-semibold text-slate-900">
            Invite Team Members
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Team
            </label>
            <select
              value={selectedTeam}
              onChange={(e) => setSelectedTeam(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Email Address
            </label>
            <div className="flex space-x-2">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && addEmail()}
                className="flex-1 border border-slate-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Enter email address"
              />
              <Button onClick={addEmail} disabled={!email}>
                Add
              </Button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Role
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          {invitedEmails.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Invited Members ({invitedEmails.length})
              </label>
              <div className="space-y-2 max-h-32 overflow-y-auto">
                {invitedEmails.map((invitedEmail, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between bg-slate-50 rounded-lg p-3"
                  >
                    <span className="text-sm text-slate-900">
                      {invitedEmail}
                    </span>
                    <button
                      onClick={() => removeEmail(invitedEmail)}
                      className="text-slate-400 hover:text-red-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end space-x-3 p-6 border-t border-slate-200">
          <Button onClick={onClose} variant="outline">
            Cancel
          </Button>
          <Button
            onClick={handleSendInvites}
            disabled={invitedEmails.length === 0 || isSending}
          >
            <Send className="w-4 h-4 mr-2" />
            {isSending
              ? "Sending..."
              : `Send ${invitedEmails.length} Invite${
                  invitedEmails.length !== 1 ? "s" : ""
                }`}
          </Button>
        </div>
      </div>
    </div>
  );
}
