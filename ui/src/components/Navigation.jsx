// components/Navigation.jsx - Updated with Dashboard Integration
import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Menu,
  X,
  ChevronDown,
  User,
  LogOut,
  Settings,
  BarChart3,
  FileText,
  Home,
} from "lucide-react";
import { utils, authAPI } from "@/lib/api";
import AuthModal from "@/components/AuthModal";

export default function Navigation({
  isAuthenticated,
  user,
  onAuthSuccess,
  onLogout,
  onDashboardClick,
  currentView = "landing",
}) {
  const [authModal, setAuthModal] = useState({ isOpen: false, mode: "login" });
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const handleLogout = async () => {
    try {
      const token = utils.getAuthToken();
      if (token) {
        await authAPI.logout(token);
      }
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      onLogout && onLogout();
      setUserMenuOpen(false);
    }
  };

  const handleAuthModalSuccess = (userData) => {
    setAuthModal({ ...authModal, isOpen: false });
    onAuthSuccess && onAuthSuccess(userData);
  };

  const navLinks = [
    { name: "Features", href: "#features" },
    { name: "Developers", href: "#developers" },
    { name: "Pricing", href: "#pricing" },
    { name: "Support", href: "#support" },
  ];

  return (
    <>
      <nav className="bg-white/90 backdrop-blur-md border-b border-slate-200 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <div className="flex items-center space-x-4">
              <div
                className="flex items-center cursor-pointer"
                onClick={() => window.location.reload()}
              >
                <div className="text-2xl font-bold text-blue-600">FileQ</div>
                <div className="ml-2 px-2 py-1 bg-blue-100 text-blue-600 text-xs rounded-full font-medium">
                  Beta
                </div>
              </div>

              {/* Navigation Breadcrumb for authenticated users */}
              {isAuthenticated && (
                <>
                  {/* <div className="hidden md:block w-px h-6 bg-slate-300"></div>
                  <div className="hidden md:flex items-center space-x-2">
                    <button
                      onClick={() =>
                        currentView === "dashboard" ? onDashboardClick() : null
                      }
                      className={`flex items-center px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                        currentView === "dashboard"
                          ? "bg-blue-100 text-blue-700"
                          : "text-slate-600 hover:text-blue-600 hover:bg-slate-100"
                      }`}
                    >
                      <BarChart3 className="w-4 h-4 mr-1" />
                      Dashboard
                    </button>
                    <button
                      className={`flex items-center px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                        currentView === "landing"
                          ? "bg-blue-100 text-blue-700"
                          : "text-slate-600 hover:text-blue-600 hover:bg-slate-100"
                      }`}
                    >
                      <FileText className="w-4 h-4 mr-1" />
                      Files
                    </button>
                  </div> */}
                </>
              )}
            </div>

            {/* Desktop Navigation */}
            {!isAuthenticated && (
              <div className="hidden md:flex items-center space-x-8">
                {navLinks.map((link) => (
                  <a
                    key={link.name}
                    href={link.href}
                    className="text-slate-600 hover:text-blue-600 transition-colors duration-200 font-medium"
                  >
                    {link.name}
                  </a>
                ))}
              </div>
            )}

            {/* Desktop Auth Section */}
            <div className="hidden md:flex items-center space-x-4">
              {!isAuthenticated ? (
                <>
                  <Button
                    variant="ghost"
                    onClick={() =>
                      setAuthModal({ isOpen: true, mode: "login" })
                    }
                    className="text-slate-600 hover:text-blue-600"
                  >
                    Sign In
                  </Button>
                  <Button
                    className="bg-blue-600 hover:bg-blue-700 text-white shadow-lg hover:shadow-xl transition-all duration-200"
                    onClick={() =>
                      setAuthModal({ isOpen: true, mode: "register" })
                    }
                  >
                    Get Started
                  </Button>
                </>
              ) : (
                <></>
                // <div className="flex items-center space-x-3">
                //   {/* Quick Actions for authenticated users */}
                //   <Button
                //     variant="outline"
                //     size="sm"
                //     onClick={onDashboardClick}
                //     className="text-slate-600 hover:text-blue-600 border-slate-200"
                //   >
                //     <BarChart3 className="w-4 h-4 mr-1" />
                //     Dashboard
                //   </Button>

                //   {/* User Menu */}
                //   <div className="relative">
                //     <button
                //       onClick={() => setUserMenuOpen(!userMenuOpen)}
                //       className="flex items-center space-x-2 p-2 rounded-lg hover:bg-slate-100 transition-colors"
                //     >
                //       <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-full flex items-center justify-center">
                //         <User className="w-4 h-4 text-white" />
                //       </div>
                //       <span className="text-slate-700 font-medium">
                //         {user?.name || "User"}
                //       </span>
                //       <ChevronDown className="w-4 h-4 text-slate-500" />
                //     </button>

                //     {/* User Dropdown */}
                //     {userMenuOpen && (
                //       <div className="absolute right-0 mt-2 w-64 bg-white rounded-xl shadow-lg border border-slate-200 py-2 z-50">
                //         <div className="px-4 py-3 border-b border-slate-100">
                //           <div className="font-medium text-slate-900">
                //             {user?.name || "User"}
                //           </div>
                //           <div className="text-sm text-slate-500">
                //             {user?.email || "user@example.com"}
                //           </div>
                //           <div className="text-xs text-green-600 mt-1 flex items-center">
                //             <div className="w-2 h-2 bg-green-500 rounded-full mr-1"></div>
                //             Premium Plan
                //           </div>
                //         </div>

                //         <button
                //           onClick={onDashboardClick}
                //           className="flex items-center w-full px-4 py-2 text-slate-700 hover:bg-slate-50 transition-colors"
                //         >
                //           <BarChart3 className="w-4 h-4 mr-3" />
                //           Dashboard
                //         </button>

                //         <a
                //           href="#"
                //           className="flex items-center px-4 py-2 text-slate-700 hover:bg-slate-50 transition-colors"
                //         >
                //           <User className="w-4 h-4 mr-3" />
                //           Profile & Account
                //         </a>

                //         <a
                //           href="#"
                //           className="flex items-center px-4 py-2 text-slate-700 hover:bg-slate-50 transition-colors"
                //         >
                //           <Settings className="w-4 h-4 mr-3" />
                //           Settings
                //         </a>

                //         <div className="border-t border-slate-100 my-1"></div>

                //         <button
                //           onClick={handleLogout}
                //           className="flex items-center w-full px-4 py-2 text-red-600 hover:bg-red-50 transition-colors"
                //         >
                //           <LogOut className="w-4 h-4 mr-3" />
                //           Sign Out
                //         </button>
                //       </div>
                //     )}
                //   </div>
                // </div>
              )}
            </div>

            {/* Mobile menu button */}
            <div className="md:hidden">
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-2 rounded-lg text-slate-600 hover:text-blue-600 hover:bg-slate-100 transition-colors"
              >
                {mobileMenuOpen ? (
                  <X className="w-6 h-6" />
                ) : (
                  <Menu className="w-6 h-6" />
                )}
              </button>
            </div>
          </div>

          {/* Mobile Navigation */}
          {mobileMenuOpen && (
            <div className="md:hidden border-t border-slate-200 py-4">
              <div className="flex flex-col space-y-4">
                {!isAuthenticated &&
                  navLinks.map((link) => (
                    <a
                      key={link.name}
                      href={link.href}
                      className="text-slate-600 hover:text-blue-600 transition-colors font-medium px-2 py-1"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      {link.name}
                    </a>
                  ))}

                {!isAuthenticated ? (
                  <div className="flex flex-col space-y-2 pt-4 border-t border-slate-200">
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setAuthModal({ isOpen: true, mode: "login" });
                        setMobileMenuOpen(false);
                      }}
                      className="justify-start text-slate-600"
                    >
                      Sign In
                    </Button>
                    <Button
                      className="bg-blue-600 hover:bg-blue-700 justify-start"
                      onClick={() => {
                        setAuthModal({ isOpen: true, mode: "register" });
                        setMobileMenuOpen(false);
                      }}
                    >
                      Get Started
                    </Button>
                  </div>
                ) : (
                  <div className="pt-4 border-t border-slate-200">
                    <div className="flex items-center space-x-3 px-2 py-2 mb-4">
                      <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-full flex items-center justify-center">
                        <User className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <div className="font-medium text-slate-900">
                          {user?.name || "User"}
                        </div>
                        <div className="text-sm text-slate-500">
                          {user?.email || "user@example.com"}
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col space-y-2">
                      <button
                        onClick={() => {
                          onDashboardClick();
                          setMobileMenuOpen(false);
                        }}
                        className="flex items-center px-2 py-2 text-slate-700 hover:text-blue-600 transition-colors"
                      >
                        <BarChart3 className="w-4 h-4 mr-3" />
                        Dashboard
                      </button>

                      <a
                        href="#"
                        className="flex items-center px-2 py-2 text-slate-700 hover:text-blue-600 transition-colors"
                      >
                        <User className="w-4 h-4 mr-3" />
                        Profile
                      </a>

                      <a
                        href="#"
                        className="flex items-center px-2 py-2 text-slate-700 hover:text-blue-600 transition-colors"
                      >
                        <Settings className="w-4 h-4 mr-3" />
                        Settings
                      </a>

                      <button
                        onClick={() => {
                          handleLogout();
                          setMobileMenuOpen(false);
                        }}
                        className="flex items-center px-2 py-2 text-red-600 hover:text-red-700 transition-colors"
                      >
                        <LogOut className="w-4 h-4 mr-3" />
                        Sign Out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </nav>

      {/* Auth Modal */}
      <AuthModal
        isOpen={authModal.isOpen}
        mode={authModal.mode}
        onClose={() => setAuthModal({ ...authModal, isOpen: false })}
        onSwitchMode={(mode) => setAuthModal({ isOpen: true, mode })}
        onSuccess={handleAuthModalSuccess}
      />
    </>
  );
}
