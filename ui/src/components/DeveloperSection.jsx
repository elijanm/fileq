// components/DeveloperSection.jsx
import React, { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Globe,
  Terminal,
  Code,
  Users,
  Palette,
  FileText,
  Check,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

export default function DeveloperSection() {
  const [activeSlide, setActiveSlide] = useState(0);

  const userCategories = [
    {
      title: "Built for Designers",
      icon: Palette,
      description:
        "Transform your creative workflow with intelligent file processing",
      features: [
        "Batch image optimization and resizing",
        "Format conversion (PNG, JPG, WebP, SVG)",
        "Color palette extraction and analysis",
        "Asset compression for web and mobile",
        "Design system asset management",
        "Automated image tagging and organization",
      ],
      gradient: "from-pink-500 to-rose-500",
      highlights: [
        "Save 70% time on asset processing",
        "Maintain quality while reducing file sizes",
        "Seamless integration with design tools",
      ],
    },
    {
      title: "Built for Developers",
      icon: Code,
      description: "Integrate powerful file processing into your applications",
      features: [
        "RESTful API with comprehensive documentation",
        "SDKs for Python, JavaScript, Go, and more",
        "Webhook support for async processing",
        "Batch processing with queue management",
        "Docker containers for easy deployment",
        "GraphQL endpoints for flexible queries",
      ],
      gradient: "from-blue-500 to-cyan-500",
      highlights: [
        "99.9% uptime SLA guaranteed",
        "Rate limits up to 10,000 requests/min",
        "Full TypeScript support included",
      ],
    },
    {
      title: "Built for Content Creators",
      icon: FileText,
      description: "Streamline your content production and sharing workflow",
      features: [
        "Video compression and format conversion",
        "Document merging and splitting",
        "Password protection and secure sharing",
        "Automated content optimization",
        "Watermarking and branding tools",
        "Analytics and engagement tracking",
      ],
      gradient: "from-purple-500 to-indigo-500",
      highlights: [
        "Reduce video sizes by up to 80%",
        "Process 4K content in under 5 minutes",
        "Share with confidence using security features",
      ],
    },
    {
      title: "Built for Teams",
      icon: Users,
      description: "Collaborate and share files with enterprise-grade security",
      features: [
        "Team workspaces and permissions",
        "Audit logs and compliance reporting",
        "SSO integration and access controls",
        "Unlimited storage and bandwidth",
        "Advanced collaboration tools",
        "Custom branding and white-labeling",
      ],
      gradient: "from-green-500 to-emerald-500",
      highlights: [
        "SOC 2 Type II certified",
        "GDPR and HIPAA compliant",
        "24/7 enterprise support included",
      ],
    },
  ];

  const nextSlide = () => {
    setActiveSlide((prev) => (prev + 1) % userCategories.length);
  };

  const prevSlide = () => {
    setActiveSlide(
      (prev) => (prev - 1 + userCategories.length) % userCategories.length
    );
  };

  return (
    <section
      id="developers"
      className="py-24 bg-gradient-to-br from-slate-50 to-blue-50"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Category Carousel */}
        <div className="mb-20">
          <div className="text-center mb-12">
            <h2 className="text-5xl font-bold text-slate-900 mb-6">
              Built for Everyone
            </h2>
            <p className="text-xl text-slate-600 max-w-3xl mx-auto">
              Discover how FileQ adapts to your unique workflow and needs. From
              designers to developers, we've got the tools you need.
            </p>
          </div>

          <div className="relative">
            {/* Carousel Container */}
            <div className="overflow-hidden rounded-3xl shadow-2xl">
              <div
                className="flex transition-transform duration-500 ease-in-out"
                style={{ transform: `translateX(-${activeSlide * 100}%)` }}
              >
                {userCategories.map((category, index) => {
                  const IconComponent = category.icon;
                  return (
                    <div key={index} className="w-full flex-shrink-0">
                      <div
                        className={`bg-gradient-to-br ${category.gradient} p-12 text-white min-h-[500px]`}
                      >
                        <div className="max-w-6xl mx-auto grid lg:grid-cols-2 gap-12 items-center">
                          <div>
                            <div className="flex items-center mb-6">
                              <div className="bg-white/20 backdrop-blur-sm rounded-2xl p-3 mr-4">
                                <IconComponent className="w-12 h-12" />
                              </div>
                              <h3 className="text-4xl font-bold">
                                {category.title}
                              </h3>
                            </div>
                            <p className="text-xl mb-8 opacity-90 leading-relaxed">
                              {category.description}
                            </p>

                            {/* Highlights */}
                            <div className="mb-8">
                              <h4 className="text-lg font-semibold mb-4 text-white/90">
                                Why Choose Us?
                              </h4>
                              <ul className="space-y-2">
                                {category.highlights.map((highlight, idx) => (
                                  <li
                                    key={idx}
                                    className="flex items-center text-white/80"
                                  >
                                    <div className="w-2 h-2 bg-white/60 rounded-full mr-3"></div>
                                    <span>{highlight}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>

                            <div className="flex space-x-4">
                              <Button
                                className="bg-white/20 hover:bg-white/30 backdrop-blur-sm border border-white/30 transition-all duration-300"
                                size="lg"
                              >
                                Get Started Free
                              </Button>
                              <Button
                                variant="outline"
                                className="border-white/30 text-white hover:bg-white/10 backdrop-blur-sm transition-all duration-300"
                              >
                                View Examples
                              </Button>
                            </div>
                          </div>

                          <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-8 border border-white/20">
                            <h4 className="text-2xl font-bold mb-6 text-white">
                              Key Features
                            </h4>
                            <div className="grid gap-4">
                              {category.features.map((feature, idx) => (
                                <div key={idx} className="flex items-start">
                                  <div className="bg-white/20 rounded-full p-1 mr-3 mt-1">
                                    <Check className="w-4 h-4 text-white" />
                                  </div>
                                  <span className="text-white/90 text-sm leading-relaxed">
                                    {feature}
                                  </span>
                                </div>
                              ))}
                            </div>

                            {/* CTA in feature box */}
                            <div className="mt-6 pt-6 border-t border-white/20">
                              <p className="text-white/70 text-sm mb-3">
                                Ready to transform your workflow?
                              </p>
                              <Button
                                size="sm"
                                className="bg-white text-slate-900 hover:bg-white/90 font-semibold"
                              >
                                Start Free Trial
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Navigation Buttons */}
            <button
              onClick={prevSlide}
              className="absolute left-4 top-1/2 transform -translate-y-1/2 bg-white/90 hover:bg-white rounded-full p-3 shadow-lg transition-all duration-300 hover:scale-110"
              aria-label="Previous slide"
            >
              <ChevronLeft className="w-6 h-6 text-slate-600" />
            </button>
            <button
              onClick={nextSlide}
              className="absolute right-4 top-1/2 transform -translate-y-1/2 bg-white/90 hover:bg-white rounded-full p-3 shadow-lg transition-all duration-300 hover:scale-110"
              aria-label="Next slide"
            >
              <ChevronRight className="w-6 h-6 text-slate-600" />
            </button>

            {/* Dots Indicator */}
            <div className="flex justify-center mt-8 space-x-2">
              {userCategories.map((_, index) => (
                <button
                  key={index}
                  onClick={() => setActiveSlide(index)}
                  className={`h-3 rounded-full transition-all duration-300 ${
                    index === activeSlide
                      ? "bg-blue-600 w-8"
                      : "bg-slate-300 hover:bg-slate-400 w-3"
                  }`}
                  aria-label={`Go to slide ${index + 1}`}
                />
              ))}
            </div>
          </div>
        </div>

        {/* API & Tools Section */}
        <div className="grid lg:grid-cols-3 gap-8 mb-16">
          <Card className="bg-white shadow-xl border-0 hover:shadow-2xl transition-all duration-300 hover:-translate-y-2">
            <CardContent className="p-8">
              <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
                <Globe className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900 mb-4">
                REST API
              </h3>
              <p className="text-slate-600 mb-6 leading-relaxed">
                Complete programmatic access to all FileQ features with our
                comprehensive REST API. Built for scale with robust error
                handling and detailed documentation.
              </p>
              <div className="mb-6">
                <div className="flex items-center text-sm text-slate-500 mb-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
                  99.9% uptime SLA
                </div>
                <div className="flex items-center text-sm text-slate-500">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                  10,000+ req/min rate limits
                </div>
              </div>
              <Button
                variant="outline"
                className="border-blue-300 text-blue-600 hover:bg-blue-50 transition-colors"
              >
                View API Docs
              </Button>
            </CardContent>
          </Card>

          <Card className="bg-white shadow-xl border-0 hover:shadow-2xl transition-all duration-300 hover:-translate-y-2">
            <CardContent className="p-8">
              <div className="w-14 h-14 bg-gradient-to-br from-green-500 to-emerald-500 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
                <Terminal className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900 mb-4">
                CLI Tool
              </h3>
              <p className="text-slate-600 mb-6 leading-relaxed">
                Powerful command-line interface for batch processing and
                automation workflows. Perfect for DevOps and CI/CD integration.
              </p>
              <div className="mb-6">
                <div className="bg-slate-100 rounded-lg p-3 mb-3">
                  <code className="text-sm text-slate-700">
                    npm install -g @fileq/cli
                  </code>
                </div>
                <div className="flex items-center text-sm text-slate-500">
                  <div className="w-2 h-2 bg-purple-500 rounded-full mr-2"></div>
                  Cross-platform support
                </div>
              </div>
              <Button
                variant="outline"
                className="border-green-300 text-green-600 hover:bg-green-50 transition-colors"
              >
                Install CLI
              </Button>
            </CardContent>
          </Card>

          <Card className="bg-white shadow-xl border-0 hover:shadow-2xl transition-all duration-300 hover:-translate-y-2">
            <CardContent className="p-8">
              <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
                <Code className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900 mb-4">SDKs</h3>
              <p className="text-slate-600 mb-6 leading-relaxed">
                Official libraries for Python, JavaScript, Go, and more to
                integrate seamlessly into your existing applications.
              </p>
              <div className="mb-6">
                <div className="flex flex-wrap gap-2 mb-3">
                  {["Python", "JavaScript", "Go", "PHP"].map((lang) => (
                    <span
                      key={lang}
                      className="px-2 py-1 bg-slate-100 text-slate-600 rounded text-xs"
                    >
                      {lang}
                    </span>
                  ))}
                </div>
                <div className="flex items-center text-sm text-slate-500">
                  <div className="w-2 h-2 bg-orange-500 rounded-full mr-2"></div>
                  TypeScript support included
                </div>
              </div>
              <Button
                variant="outline"
                className="border-blue-300 text-blue-600 hover:bg-blue-50 transition-colors"
              >
                Browse SDKs
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Code Example */}
        <Card className="bg-slate-900 border-0 shadow-2xl overflow-hidden">
          <CardContent className="p-0">
            <div className="flex items-center justify-between p-6 pb-4">
              <h3 className="text-2xl font-bold text-white">
                Quick Start Example
              </h3>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              </div>
            </div>

            {/* Tabs */}
            <div className="px-6 mb-4">
              <div className="flex space-x-1 bg-slate-800 p-1 rounded-lg w-fit">
                <button className="px-3 py-1 bg-slate-700 text-white rounded text-sm font-medium">
                  JavaScript
                </button>
                <button className="px-3 py-1 text-slate-400 hover:text-white rounded text-sm font-medium transition-colors">
                  Python
                </button>
                <button className="px-3 py-1 text-slate-400 hover:text-white rounded text-sm font-medium transition-colors">
                  cURL
                </button>
              </div>
            </div>

            <div className="bg-slate-800 mx-6 mb-6 rounded-lg overflow-hidden">
              <div className="p-6 overflow-x-auto">
                <pre className="text-green-400 text-sm leading-relaxed">
                  <code>{`// Upload and process a file with FileQ API
import { FileQ } from '@fileq/sdk';

const client = new FileQ({
  apiKey: 'your-api-key-here',
  baseURL: 'http://localhost:8000'
});

// Upload file with progress tracking
const uploadFile = async (file) => {
  try {
    const result = await client.upload(file, {
      tosAccept: true,
      onProgress: (progress) => {
        console.log(\`Upload: \${progress}%\`);
      }
    });
    
    console.log('✅ Upload successful!');
    console.log('📁 File ID:', result.file_id);
    console.log('🔗 Download URL:', result.download_url);
    console.log('🛠️ Available tools:', result.tools.length);
    
    // Use available tools
    for (const tool of result.tools) {
      console.log(\`  • \${tool.name}: \${tool.action}\`);
    }
    
    return result;
  } catch (error) {
    console.error('❌ Upload failed:', error.message);
  }
};

// Example: Convert to PDF
const convertToPDF = async (fileId) => {
  const pdf = await client.tools.convertToPDF(fileId);
  console.log('📄 PDF ready:', pdf.download_url);
};`}</code>
                </pre>
              </div>
            </div>

            {/* Feature callouts */}
            <div className="px-6 pb-6">
              <div className="grid md:grid-cols-3 gap-4">
                <div className="flex items-center text-white/80">
                  <div className="w-2 h-2 bg-green-400 rounded-full mr-3"></div>
                  <span className="text-sm">Type-safe SDK</span>
                </div>
                <div className="flex items-center text-white/80">
                  <div className="w-2 h-2 bg-blue-400 rounded-full mr-3"></div>
                  <span className="text-sm">Progress tracking</span>
                </div>
                <div className="flex items-center text-white/80">
                  <div className="w-2 h-2 bg-purple-400 rounded-full mr-3"></div>
                  <span className="text-sm">Error handling</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Integration Examples */}
        <div className="mt-16 text-center">
          <h3 className="text-3xl font-bold text-slate-900 mb-8">
            Trusted by developers at
          </h3>
          <div className="flex flex-wrap justify-center items-center gap-12 opacity-60">
            {/* Company logos would go here */}
            <div className="text-2xl font-bold text-slate-400">Google</div>
            <div className="text-2xl font-bold text-slate-400">Microsoft</div>
            <div className="text-2xl font-bold text-slate-400">Netflix</div>
            <div className="text-2xl font-bold text-slate-400">Shopify</div>
            <div className="text-2xl font-bold text-slate-400">Stripe</div>
          </div>
        </div>
      </div>
    </section>
  );
}
