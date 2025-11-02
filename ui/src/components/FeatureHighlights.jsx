// components/FeatureHighlights.jsx
import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Zap, Shield, Sparkles } from "lucide-react";

export default function FeatureHighlights() {
  return (
    <div className="mt-24 grid md:grid-cols-3 gap-8">
      <Card className="bg-white shadow-xl border-0 hover:shadow-2xl transition-shadow duration-300">
        <CardContent className="p-8 text-center">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <Zap className="w-8 h-8 text-white" />
          </div>
          <h3 className="text-2xl font-bold text-slate-900 mb-4">
            Lightning Fast
          </h3>
          <p className="text-slate-600">
            Process files in seconds with our optimized algorithms and cloud
            infrastructure.
          </p>
        </CardContent>
      </Card>

      <Card className="bg-white shadow-xl border-0 hover:shadow-2xl transition-shadow duration-300">
        <CardContent className="p-8 text-center">
          <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-emerald-500 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h3 className="text-2xl font-bold text-slate-900 mb-4">
            Secure & Private
          </h3>
          <p className="text-slate-600">
            Your files are encrypted and automatically deleted. We never store
            your data permanently.
          </p>
        </CardContent>
      </Card>

      <Card className="bg-white shadow-xl border-0 hover:shadow-2xl transition-shadow duration-300">
        <CardContent className="p-8 text-center">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <h3 className="text-2xl font-bold text-slate-900 mb-4">AI-Powered</h3>
          <p className="text-slate-600">
            Smart file analysis and optimization powered by cutting-edge AI
            technology.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
