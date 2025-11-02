import React from "react";
import {
  CreditCard,
  Check,
  AlertCircle,
  Eye,
  EyeOff,
  Copy,
  RefreshCw,
  ExternalLink,
} from "lucide-react";

export default function StripeConfig({
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
    console.log("Saving Stripe config:", config);
    alert("Stripe configuration saved successfully!");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
          <CreditCard className="w-5 h-5 text-blue-600" />
        </div>
        <div>
          <h3 className="text-xl font-semibold text-slate-900">
            Stripe Configuration
          </h3>
          <p className="text-sm text-slate-600">
            Accept credit cards, debit cards, and digital wallets worldwide
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
            { id: "test", label: "Test Mode" },
            { id: "live", label: "Live Mode" },
          ].map((env) => (
            <button
              key={env.id}
              onClick={() => updateConfig({ environment: env.id })}
              className={`px-4 py-2 rounded-lg border font-medium transition-colors ${
                config.environment === env.id
                  ? "border-blue-500 bg-blue-50 text-blue-700"
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
            Publishable Key
          </label>
          <input
            type="text"
            value={config.publishableKey}
            onChange={(e) => updateConfig({ publishableKey: e.target.value })}
            className="w-full border border-slate-200 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder={`pk_${config.environment}_...`}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Secret Key
          </label>
          <div className="relative">
            <input
              type={showSecrets ? "text" : "password"}
              value={config.secretKey}
              onChange={(e) => updateConfig({ secretKey: e.target.value })}
              className="w-full border border-slate-200 rounded-lg px-4 py-3 pr-10 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder={`sk_${config.environment}_...`}
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
            Webhook Endpoint Secret
          </label>
          <div className="relative">
            <input
              type={showSecrets ? "text" : "password"}
              value={config.webhookSecret}
              onChange={(e) => updateConfig({ webhookSecret: e.target.value })}
              className="w-full border border-slate-200 rounded-lg px-4 py-3 pr-10 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="whsec_..."
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
          Add this URL to your Stripe webhook endpoints:
        </p>
        <div className="bg-slate-100 rounded-lg p-3 flex items-center justify-between">
          <code className="text-sm font-mono text-slate-700">
            https://api.fileq.com/webhook/stripe
          </code>
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              copyToClipboard("https://api.fileq.com/webhook/stripe")
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
              isTestingConnection || !config.publishableKey || !config.secretKey
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
                ? "Connection successful! Stripe credentials are valid."
                : "Connection failed. Please check your API keys."}
            </span>
          </div>
        )}
      </div>

      {/* Supported Payment Methods */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-medium text-blue-900 mb-3">
          Supported Payment Methods
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm text-blue-800">
          {[
            "Visa",
            "Mastercard",
            "American Express",
            "Discover",
            "Apple Pay",
            "Google Pay",
            "SEPA Direct Debit",
            "ACH payments",
          ].map((method) => (
            <div key={method} className="flex items-center space-x-1">
              <Check className="w-3 h-3" />
              <span>{method}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center space-x-4 pt-4 border-t border-slate-200">
        <Button onClick={handleSave}>Save Configuration</Button>
        <Button variant="outline">
          <ExternalLink className="w-4 h-4 mr-2" />
          Stripe Dashboard
        </Button>
      </div>
    </div>
  );
}
