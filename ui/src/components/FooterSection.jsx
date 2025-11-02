// components/FooterSection.jsx
import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Mail,
  Phone,
  MapPin,
  Github,
  Twitter,
  Linkedin,
  Instagram,
  Facebook,
  ArrowRight,
  FileText,
  Shield,
  Globe,
  Zap,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";

export default function FooterSection() {
  const [email, setEmail] = useState("");
  const [subscribeStatus, setSubscribeStatus] = useState("idle"); // idle, loading, success, error
  const [subscribeMessage, setSubscribeMessage] = useState("");
  const currentYear = new Date().getFullYear();

  const handleNewsletterSubmit = async (e) => {
    e.preventDefault();

    if (!email) {
      setSubscribeStatus("error");
      setSubscribeMessage("Please enter your email address");
      return;
    }

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setSubscribeStatus("error");
      setSubscribeMessage("Please enter a valid email address");
      return;
    }

    setSubscribeStatus("loading");
    setSubscribeMessage("");

    try {
      // Simulate API call - replace with actual newsletter subscription
      await new Promise((resolve) => setTimeout(resolve, 1500));

      setSubscribeStatus("success");
      setSubscribeMessage("Successfully subscribed! Welcome to FileQ updates.");
      setEmail("");

      // Reset status after 3 seconds
      setTimeout(() => {
        setSubscribeStatus("idle");
        setSubscribeMessage("");
      }, 3000);
    } catch (error) {
      setSubscribeStatus("error");
      setSubscribeMessage("Subscription failed. Please try again.");

      setTimeout(() => {
        setSubscribeStatus("idle");
        setSubscribeMessage("");
      }, 3000);
    }
  };

  const productLinks = [
    { name: "Features", href: "#features" },
    { name: "Pricing", href: "#pricing" },
    { name: "API Documentation", href: "/docs/api" },
    { name: "CLI Tool", href: "/cli" },
    { name: "Integrations", href: "/integrations" },
    { name: "Mobile Apps", href: "/mobile" },
    { name: "Desktop Apps", href: "/desktop" },
    { name: "Browser Extension", href: "/extension" },
  ];

  const companyLinks = [
    { name: "About Us", href: "/about" },
    { name: "Blog", href: "/blog" },
    { name: "Careers", href: "/careers" },
    { name: "Press Kit", href: "/press" },
    { name: "Partners", href: "/partners" },
    { name: "Investors", href: "/investors" },
    { name: "Contact", href: "/contact" },
    { name: "Brand Guidelines", href: "/brand" },
  ];

  const supportLinks = [
    { name: "Help Center", href: "/help" },
    { name: "Community Forum", href: "/community" },
    { name: "Status Page", href: "https://status.fileq.com" },
    { name: "Report a Bug", href: "/bug-report" },
    { name: "Feature Requests", href: "/feature-requests" },
    { name: "Security", href: "/security" },
    { name: "System Status", href: "/status" },
    { name: "Release Notes", href: "/releases" },
  ];

  const developerLinks = [
    { name: "API Reference", href: "/docs" },
    { name: "SDKs", href: "/sdks" },
    { name: "Webhooks", href: "/webhooks" },
    { name: "Code Examples", href: "/examples" },
    { name: "Postman Collection", href: "/postman" },
    { name: "OpenAPI Spec", href: "/openapi" },
  ];

  const socialLinks = [
    {
      icon: Twitter,
      href: "https://twitter.com/fileq",
      label: "Twitter",
      color: "hover:text-blue-400",
    },
    {
      icon: Github,
      href: "https://github.com/fileq",
      label: "GitHub",
      color: "hover:text-gray-300",
    },
    {
      icon: Linkedin,
      href: "https://linkedin.com/company/fileq",
      label: "LinkedIn",
      color: "hover:text-blue-300",
    },
    {
      icon: Instagram,
      href: "https://instagram.com/fileq",
      label: "Instagram",
      color: "hover:text-pink-400",
    },
    {
      icon: Facebook,
      href: "https://facebook.com/fileq",
      label: "Facebook",
      color: "hover:text-blue-500",
    },
  ];

  const trustIndicators = [
    {
      icon: Shield,
      title: "SOC 2 Certified",
      description: "Enterprise-grade security",
      color: "bg-blue-600/20 text-blue-400",
    },
    {
      icon: FileText,
      title: "GDPR Compliant",
      description: "Privacy by design",
      color: "bg-green-600/20 text-green-400",
    },
    {
      icon: Globe,
      title: "Global Infrastructure",
      description: "99.9% uptime guarantee",
      color: "bg-purple-600/20 text-purple-400",
    },
  ];

  return (
    <footer className="bg-slate-900 text-white relative overflow-hidden">
      {/* Background Elements */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-cyan-500 rounded-full blur-3xl"></div>
      </div>

      {/* Newsletter Section */}
      <div className="border-b border-slate-800 relative z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid lg:grid-cols-2 gap-8 items-center">
            <div>
              <h3 className="text-3xl font-bold mb-4 bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                Stay updated with FileQ
              </h3>
              <p className="text-slate-400 text-lg leading-relaxed">
                Get the latest updates on new features, security improvements,
                file processing tips, and exclusive insights from our
                engineering team. Join 25,000+ subscribers.
              </p>
              <div className="flex items-center mt-4 text-sm text-slate-500">
                <CheckCircle2 className="w-4 h-4 mr-2 text-green-400" />
                <span>Weekly updates • No spam • Unsubscribe anytime</span>
              </div>
            </div>

            <div>
              <form
                onSubmit={handleNewsletterSubmit}
                className="flex flex-col sm:flex-row gap-4"
              >
                <div className="flex-1 relative">
                  <input
                    type="email"
                    placeholder="Enter your email address"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors placeholder-slate-500"
                    disabled={subscribeStatus === "loading"}
                  />
                  <Mail className="absolute right-3 top-3 w-5 h-5 text-slate-500" />
                </div>
                <Button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-700 px-6 py-3 font-semibold transition-all hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={subscribeStatus === "loading"}
                >
                  {subscribeStatus === "loading" ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Subscribing...
                    </>
                  ) : (
                    <>
                      Subscribe
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </>
                  )}
                </Button>
              </form>

              {/* Subscription Status */}
              {subscribeMessage && (
                <div
                  className={`mt-4 p-3 rounded-lg flex items-center text-sm ${
                    subscribeStatus === "success"
                      ? "bg-green-900/20 border border-green-800 text-green-400"
                      : "bg-red-900/20 border border-red-800 text-red-400"
                  }`}
                >
                  {subscribeStatus === "success" ? (
                    <CheckCircle2 className="w-4 h-4 mr-2 flex-shrink-0" />
                  ) : (
                    <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
                  )}
                  {subscribeMessage}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Footer Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 relative z-10">
        <div className="grid md:grid-cols-2 lg:grid-cols-6 gap-8">
          {/* Company Info */}
          <div className="lg:col-span-2">
            <div className="flex items-center mb-6">
              <div className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                FileQ
              </div>
              <div className="ml-3 px-2 py-1 bg-blue-600 text-white text-xs rounded-full font-semibold">
                Beta
              </div>
            </div>

            <p className="text-slate-400 mb-6 leading-relaxed">
              Transform files with AI-powered tools. Simple, fast, and secure
              file processing for individuals, teams, and enterprises worldwide.
              Processing 10M+ files monthly.
            </p>

            {/* Contact Info */}
            <div className="space-y-3 mb-6">
              <div className="flex items-center text-slate-400 hover:text-white transition-colors">
                <Mail className="w-4 h-4 mr-3 text-blue-400" />
                <a href="mailto:hello@fileq.com">hello@fileq.com</a>
              </div>
              <div className="flex items-center text-slate-400 hover:text-white transition-colors">
                <Phone className="w-4 h-4 mr-3 text-green-400" />
                <a href="tel:+15551234567">+1 (555) 123-4567</a>
              </div>
              <div className="flex items-center text-slate-400">
                <MapPin className="w-4 h-4 mr-3 text-purple-400" />
                <span>San Francisco, CA • Remote-first</span>
              </div>
            </div>

            {/* Social Links */}
            <div className="flex space-x-4">
              {socialLinks.map(({ icon: Icon, href, label, color }) => (
                <a
                  key={label}
                  href={href}
                  className={`w-10 h-10 bg-slate-800 rounded-lg flex items-center justify-center hover:bg-slate-700 transition-all duration-300 group ${color} hover:scale-110`}
                  aria-label={label}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Icon className="w-5 h-5 text-slate-400 group-hover:text-current transition-colors" />
                </a>
              ))}
            </div>
          </div>

          {/* Product Links */}
          <div>
            <h4 className="text-lg font-semibold mb-6 text-white flex items-center">
              <Zap className="w-5 h-5 mr-2 text-blue-400" />
              Product
            </h4>
            <ul className="space-y-3">
              {productLinks.map((item) => (
                <li key={item.name}>
                  <a
                    href={item.href}
                    className="text-slate-400 hover:text-white transition-colors hover:translate-x-1 transform duration-200 block"
                  >
                    {item.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Company Links */}
          <div>
            <h4 className="text-lg font-semibold mb-6 text-white flex items-center">
              <Globe className="w-5 h-5 mr-2 text-green-400" />
              Company
            </h4>
            <ul className="space-y-3">
              {companyLinks.map((item) => (
                <li key={item.name}>
                  <a
                    href={item.href}
                    className="text-slate-400 hover:text-white transition-colors hover:translate-x-1 transform duration-200 block"
                  >
                    {item.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Support Links */}
          <div>
            <h4 className="text-lg font-semibold mb-6 text-white flex items-center">
              <Shield className="w-5 h-5 mr-2 text-purple-400" />
              Support
            </h4>
            <ul className="space-y-3">
              {supportLinks.map((item) => (
                <li key={item.name}>
                  <a
                    href={item.href}
                    className="text-slate-400 hover:text-white transition-colors hover:translate-x-1 transform duration-200 block"
                    target={item.href.startsWith("http") ? "_blank" : undefined}
                    rel={
                      item.href.startsWith("http")
                        ? "noopener noreferrer"
                        : undefined
                    }
                  >
                    {item.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Developer Links */}
          <div>
            <h4 className="text-lg font-semibold mb-6 text-white flex items-center">
              <FileText className="w-5 h-5 mr-2 text-orange-400" />
              Developers
            </h4>
            <ul className="space-y-3">
              {developerLinks.map((item) => (
                <li key={item.name}>
                  <a
                    href={item.href}
                    className="text-slate-400 hover:text-white transition-colors hover:translate-x-1 transform duration-200 block"
                  >
                    {item.name}
                  </a>
                </li>
              ))}
            </ul>

            {/* Developer Badge */}
            <div className="mt-6 p-3 bg-slate-800/50 border border-slate-700 rounded-lg">
              <div className="flex items-center text-orange-400 text-sm font-medium mb-1">
                <Github className="w-4 h-4 mr-2" />
                Open Source
              </div>
              <p className="text-slate-400 text-xs">
                Some components available on GitHub
              </p>
            </div>
          </div>
        </div>

        {/* Trust Indicators */}
        <div className="mt-16 pt-8 border-t border-slate-800">
          <div className="grid md:grid-cols-3 gap-8 mb-12">
            {trustIndicators.map((indicator, index) => {
              const IconComponent = indicator.icon;
              return (
                <div
                  key={index}
                  className="flex items-center group cursor-pointer"
                >
                  <div
                    className={`${indicator.color} rounded-full p-3 mr-4 group-hover:scale-110 transition-transform`}
                  >
                    <IconComponent className="w-6 h-6" />
                  </div>
                  <div>
                    <div className="font-semibold text-white group-hover:text-blue-400 transition-colors">
                      {indicator.title}
                    </div>
                    <div className="text-slate-400 text-sm">
                      {indicator.description}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Awards & Certifications */}
          <div className="text-center mb-8">
            <h4 className="text-white font-semibold mb-4">
              Awards & Recognition
            </h4>
            <div className="flex flex-wrap justify-center items-center gap-6 opacity-60">
              <div className="text-slate-400 text-sm">
                🏆 Product Hunt #1 Product of the Day
              </div>
              <div className="text-slate-400 text-sm">
                ⭐ G2 High Performer 2024
              </div>
              <div className="text-slate-400 text-sm">
                🛡️ SOC 2 Type II Certified
              </div>
              <div className="text-slate-400 text-sm">🔒 GDPR Compliant</div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-slate-800 relative z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="text-slate-400 text-sm mb-4 md:mb-0 flex items-center">
              <span>&copy; {currentYear} FileQ, Inc. All rights reserved.</span>
              <div className="ml-4 flex items-center text-xs">
                <div className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></div>
                <span>All systems operational</span>
              </div>
            </div>

            <div className="flex flex-wrap items-center space-x-6 text-sm">
              <a
                href="/privacy"
                className="text-slate-400 hover:text-white transition-colors"
              >
                Privacy Policy
              </a>
              <a
                href="/terms"
                className="text-slate-400 hover:text-white transition-colors"
              >
                Terms of Service
              </a>
              <a
                href="/cookies"
                className="text-slate-400 hover:text-white transition-colors"
              >
                Cookie Policy
              </a>
              <a
                href="/acceptable-use"
                className="text-slate-400 hover:text-white transition-colors"
              >
                Acceptable Use
              </a>
              <div className="text-slate-600">•</div>
              <div className="text-slate-400 flex items-center">
                Made with <span className="text-red-400 mx-1">❤️</span> in San
                Francisco
              </div>
            </div>
          </div>

          {/* Legal Notice */}
          <div className="mt-4 pt-4 border-t border-slate-800 text-center">
            <p className="text-slate-500 text-xs max-w-4xl mx-auto">
              FileQ is a registered trademark of FileQ, Inc. Other trademarks
              and trade names are the property of their respective owners. By
              using our service, you agree to our Terms of Service and Privacy
              Policy. We use cookies to enhance your experience and analyze
              usage.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
