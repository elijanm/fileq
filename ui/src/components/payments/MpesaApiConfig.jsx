import React from "react";
import {
  Smartphone,
  Check,
  AlertCircle,
  Eye,
  EyeOff,
  RefreshCw,
  ExternalLink,
} from "lucide-react";

export default function MpesaApiConfig({
  config,
  updateConfig,
  showSecrets,
  setShowSecrets,
  isTestingConnection,
  connectionStatus,
  onTestConnection,
  Button,
  user,
}) {
  const handleSave = () => {
    console.log("Saving M-Pesa API config:", config);
    alert("M-Pesa API configuration saved successfully!");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
          <Smartphone className="w-5 h-5 text-green-600" />
        </div>
        <div>
          <h3 className="text-xl font-semibold text-slate-900">
            M-Pesa API Configuration
          </h3>
          <p className="text-sm text-slate-600">
            Configure your Safaricom M-Pesa API credentials
          </p>
        </div>
      </div>

      {/* Environment Selection */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-3">
          Environment
        </label>
        <div className="flex space-x-3">
          {["sandbox", "production"].map((env) => (
            <button
              key={env}
              onClick={() => updateConfig({ environment: env })}
              className={`px-4 py-2 rounded-lg border font-medium capitalize transition-colors ${
                config.environment === env
                  ? "border-green-500 bg-green-50 text-green-700"
                  : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
              }`}
            >
              {env}
            </button>
          ))}
        </div>
      </div>

      {/* Credentials Form */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Consumer Key
          </label>
          <input
            type="text"
            value={config.consumerKey}
            onChange={(e) => updateConfig({ consumerKey: e.target.value })}
            className="w-full border border-slate-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-green-500 focus:border-transparent"
            placeholder="Enter consumer key"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Consumer Secret
          </label>
          <div className="relative">
            <input
              type={showSecrets ? "text" : "password"}
              value={config.consumerSecret}
              onChange={(e) => updateConfig({ consumerSecret: e.target.value })}
              className="w-full border border-slate-200 rounded-lg px-4 py-3 pr-10 focus:ring-2 focus:ring-green-500 focus:border-transparent"
              placeholder="Enter consumer secret"
            />
            <button
              onClick={() => setShowSecrets(!showSecrets)}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              {showSecrets ? (
                <EyeOff className="w-4 h-4" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Business Short Code
          </label>
          <input
            type="text"
            value={config.shortcode}
            onChange={(e) => updateConfig({ shortcode: e.target.value })}
            className="w-full border border-slate-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-green-500 focus:border-transparent"
            placeholder="e.g., 174379"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Passkey
          </label>
          <div className="relative">
            <input
              type={showSecrets ? "text" : "password"}
              value={config.passkey}
              onChange={(e) => updateConfig({ passkey: e.target.value })}
              className="w-full border border-slate-200 rounded-lg px-4 py-3 pr-10 focus:ring-2 focus:ring-green-500 focus:border-transparent"
              placeholder="Enter passkey"
            />
            <button
              onClick={() => setShowSecrets(!showSecrets)}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              {showSecrets ? (
                <EyeOff className="w-4 h-4" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Connection Test */}
      <div className="bg-slate-50 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-slate-900">Connection Test</h4>
          <Button
            onClick={onTestConnection}
            disabled={
              isTestingConnection ||
              !config.consumerKey ||
              !config.consumerSecret
            }
            variant="outline"
            size="sm"
          >
            {isTestingConnection ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Testing...
              </>
            ) : (
              "Test Connection"
            )}
          </Button>
        </div>

        {connectionStatus && (
          <div
            className={`flex items-center space-x-2 ${
              connectionStatus === "success" ? "text-green-600" : "text-red-600"
            }`}
          >
            {connectionStatus === "success" ? (
              <Check className="w-4 h-4" />
            ) : (
              <AlertCircle className="w-4 h-4" />
            )}
            <span className="text-sm">
              {connectionStatus === "success"
                ? "Connection successful! API credentials are valid."
                : "Connection failed. Please check your credentials."}
            </span>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center space-x-4 pt-4 border-t border-slate-200">
        <Button onClick={handleSave}>Save Configuration</Button>
        <Button variant="outline">
          <ExternalLink className="w-4 h-4 mr-2" />
          View Documentation
        </Button>
      </div>
    </div>
  );
}
