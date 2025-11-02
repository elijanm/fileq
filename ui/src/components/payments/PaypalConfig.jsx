import React from "react";
import {
  Globe,
  Check,
  AlertCircle,
  Eye,
  EyeOff,
  Copy,
  RefreshCw,
  ExternalLink,
} from "lucide-react";

export default function PaypalConfig({
  config,
  updateConfig,
  showSecrets,
  setShowSecrets,
  isTestingConnection,
  connectionStatus,
  onTestConnection,
  Button,
  copyToClipboard,
}) {
  const handleSave = () => {
    console.log("Saving PayPal config:", config);
    alert("PayPal configuration saved successfully!");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
          <Globe className="w-5 h-5 text-purple-600" />
        </div>
        <div>
          <h3 className="text-xl font-semibold text-slate-900">
            PayPal Configuration
          </h3>
          <p className="text-sm text-slate-600">
            Accept PayPal payments and PayPal Credit
          </p>
        </div>
      </div>

      {/* Environment Selection */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-3">
          Environment
        </label>
        <div className="flex space-x-3">
          {[
            { id: "sandbox", label: "Sandbox" },
            { id: "production", label: "Production" },
          ].map((env) => (
            <button
              key={env.id}
              onClick={() => updateConfig({ environment: env.id })}
              className={`px-4 py-2 rounded-lg border font-medium transition-colors ${
                config.environment === env.id
                  ? "border-purple-500 bg-purple-50 text-purple-700"
                  : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
              }`}
            >
              {env.label}
            </button>
          ))}
        </div>
      </div>

      {/* Credentials Form */}
      <div className="grid grid-cols-1 gap-6">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Client ID
          </label>
          <input
            type="text"
            value={config.clientId}
            onChange={(e) => updateConfig({ clientId: e.target.value })}
            className="w-full border border-slate-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            placeholder="Your PayPal Client ID"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Client Secret
          </label>
          <div className="relative">
            <input
              type={showSecrets ? "text" : "password"}
              value={config.clientSecret}
              onChange={(e) => updateConfig({ clientSecret: e.target.value })}
              className="w-full border border-slate-200 rounded-lg px-4 py-3 pr-10 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              placeholder="Your PayPal Client Secret"
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

      {/* Webhook URL */}
      <div className="bg-slate-50 rounded-lg p-4">
        <h4 className="font-medium text-slate-900 mb-2">Webhook URL</h4>
        <p className="text-sm text-slate-600 mb-3">
          Add this URL to your PayPal webhook notifications:
        </p>
        <div className="bg-slate-100 rounded-lg p-3 flex items-center justify-between">
          <code className="text-sm font-mono text-slate-700">
            https://api.fileq.com/webhook/paypal
          </code>
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              copyToClipboard("https://api.fileq.com/webhook/paypal")
            }
          >
            <Copy className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Connection Test */}
      <div className="bg-slate-50 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-slate-900">Connection Test</h4>
          <Button
            onClick={onTestConnection}
            disabled={
              isTestingConnection || !config.clientId || !config.clientSecret
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
                ? "Connection successful! PayPal credentials are valid."
                : "Connection failed. Please check your credentials."}
            </span>
          </div>
        )}
      </div>

      {/* Supported Features */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <h4 className="font-medium text-purple-900 mb-3">PayPal Features</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-purple-800">
          {[
            "PayPal Balance",
            "PayPal Credit",
            "Bank Transfers",
            "Credit Cards via PayPal",
          ].map((feature) => (
            <div key={feature} className="flex items-center space-x-2">
              <Check className="w-4 h-4" />
              <span>{feature}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center space-x-4 pt-4 border-t border-slate-200">
        <Button onClick={handleSave}>Save Configuration</Button>
        <Button variant="outline">
          <ExternalLink className="w-4 h-4 mr-2" />
          PayPal Developer
        </Button>
      </div>
    </div>
  );
}
