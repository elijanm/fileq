// lib/api.js - API Functions
const BASE_URL = "http://localhost:8000";

// Auth API functions
export const authAPI = {
  register: async (data) => {
    const response = await fetch(`${BASE_URL}/api/v1/auth/register`, {
      method: "POST",
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || "Registration failed");
    }

    return response.json();
  },

  login: async (data) => {
    const response = await fetch(`${BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || error.message || "Login failed");
    }

    return response.json();
  },

  forgotPassword: async (email) => {
    const response = await fetch(
      `${BASE_URL}/api/v1/auth/forgot-password?email=${encodeURIComponent(
        email
      )}`,
      {
        method: "POST",
        headers: {
          accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || "Password reset failed");
    }

    return response.json();
  },

  logout: async (token) => {
    const response = await fetch(`${BASE_URL}/api/v1/auth/logout`, {
      method: "POST",
      headers: {
        accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || "Logout failed");
    }

    return response.json();
  },
};

// Upload API
export const uploadAPI = {
  uploadFile: async (file, tosAccept = true) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("tos_accept", tosAccept);

    const response = await fetch(`${BASE_URL}/uploads/media`, {
      method: "POST",
      headers: {
        accept: "application/json",
        // Don't set Content-Type for FormData, let browser set it with boundary
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || "Upload failed");
    }

    return response.json();
  },
};

// File operations API
export const fileAPI = {
  downloadFile: async (downloadUrl) => {
    const response = await fetch(downloadUrl);
    if (!response.ok) {
      throw new Error("Download failed");
    }
    return response.blob();
  },

  deleteFile: async (fileId, token) => {
    const response = await fetch(`${BASE_URL}/files/${fileId}`, {
      method: "DELETE",
      headers: {
        accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || "Delete failed");
    }

    return response.json();
  },
};

// Tools API for file processing
export const toolsAPI = {
  convertToPDF: async (fileId, token) => {
    const response = await fetch(`${BASE_URL}/tools/convert/pdf`, {
      method: "POST",
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ file_id: fileId }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || "Conversion failed");
    }

    return response.json();
  },

  passwordProtect: async (fileId, password, token) => {
    const response = await fetch(`${BASE_URL}/tools/password-protect`, {
      method: "POST",
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ file_id: fileId, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || "Password protection failed");
    }

    return response.json();
  },

  shareFile: async (fileId, options, token) => {
    const response = await fetch(`${BASE_URL}/tools/share`, {
      method: "POST",
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ file_id: fileId, ...options }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || "Sharing failed");
    }

    return response.json();
  },
};

// Utility functions
export const utils = {
  getAuthToken: () => localStorage.getItem("access_token"),

  setAuthToken: (token) => localStorage.setItem("access_token", token),

  removeAuthToken: () => localStorage.removeItem("access_token"),

  isAuthenticated: () => !!localStorage.getItem("access_token"),
  setUser: (user) => localStorage.setItem("user_info", user),
  getUser: () => localStorage.getItem("user_info"),

  formatFileSize: (bytes) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  },

  getFileIcon: (fileName) => {
    const ext = fileName.split(".").pop().toLowerCase();
    const iconMap = {
      pdf: "file-pdf",
      doc: "file-alt",
      docx: "file-alt",
      xls: "file-excel",
      xlsx: "file-excel",
      ppt: "file-powerpoint",
      pptx: "file-powerpoint",
      jpg: "file-image",
      jpeg: "file-image",
      png: "file-image",
      gif: "file-image",
      mp4: "file-video",
      avi: "file-video",
      mp3: "file-audio",
      wav: "file-audio",
      zip: "file-archive",
      rar: "file-archive",
    };
    return iconMap[ext] || "file-alt";
  },
};
