import React, { useState } from "react";
import { CreditCard, Smartphone, Globe, AlertCircle } from "lucide-react";

// Import components (in separate files)
import MpesaApiConfig from "@/components/payments/MpesaApiConfig";
import MpesaSmsConfig from "@/components/payments/MpesaSmsConfig";
import StripeConfig from "@/components/payments/StripeConfig";
import PaypalConfig from "@/components/payments/PaypalConfig";

export default function PaymentIntegrationSettings({
  user,
  userLocation = "KE",
}) {
  // State management
  const [selectedMethod, setSelectedMethod] = useState("mpesa-api");
  const [showSecrets, setShowSecrets] = useState(false);
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState(null);

  // Payment method configurations
  const [paymentConfigs, setPaymentConfigs] = useState({
    "mpesa-api": {
      consumerKey: "",
      consumerSecret: "",
      shortcode: "",
      passkey: "",
      environment: "sandbox",
    },
    "mpesa-sms": {
      enabled: false,
    },
    stripe: {
      publishableKey: "",
      secretKey: "",
      webhookSecret: "",
      environment: "test",
    },
    paypal: {
      clientId: "",
      clientSecret: "",
      environment: "sandbox",
    },
  });

  // Button component
  const Button = ({
    children,
    onClick,
    variant = "default",
    size = "default",
    className = "",
    disabled = false,
  }) => {
    const baseClass =
      "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
    const variants = {
      default: "bg-blue-600 text-white hover:bg-blue-700",
      outline:
        "border border-slate-200 bg-white hover:bg-slate-100 text-slate-900",
      ghost: "hover:bg-slate-100 text-slate-600",
    };
    const sizes = {
      default: "h-10 py-2 px-4",
      sm: "h-9 px-3 text-sm",
    };

    return (
      <button
        className={`${baseClass} ${variants[variant]} ${sizes[size]} ${className}`}
        onClick={onClick}
        disabled={disabled}
      >
        {children}
      </button>
    );
  };

  // Payment method definitions
  const paymentMethods = [
    {
      id: "mpesa-api",
      name: "M-Pesa API",
      description: "Direct API integration with Safaricom M-Pesa",
      icon: Smartphone,
      color: "green",
      available: userLocation === "KE",
      recommended: userLocation === "KE",
    },
    {
      id: "mpesa-sms",
      name: "M-Pesa SMS",
      description: "Real-time payment verification via MpesaSync App",
      icon: Smartphone,
      color: "green",
      available: userLocation === "KE",
    },
    {
      id: "stripe",
      name: "Stripe",
      description: "Credit cards, debit cards, and digital wallets",
      icon: CreditCard,
      color: "blue",
      available: true,
    },
    {
      id: "paypal",
      name: "PayPal",
      description: "PayPal payments and PayPal Credit",
      icon: Globe,
      color: "purple",
      available: true,
    },
  ];

  // Update configuration for a specific payment method
  const updateConfig = (method, updates) => {
    setPaymentConfigs((prev) => ({
      ...prev,
      [method]: { ...prev[method], ...updates },
    }));
  };

  // Test connection handler
  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    setConnectionStatus(null);

    // Simulate API call
    setTimeout(() => {
      setIsTestingConnection(false);
      setConnectionStatus(Math.random() > 0.3 ? "success" : "error");
    }, 2000);
  };

  // Copy to clipboard
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    alert("Copied to clipboard!");
  };

  // Component props for each config
  const configProps = {
    showSecrets,
    setShowSecrets,
    isTestingConnection,
    connectionStatus,
    onTestConnection: handleTestConnection,
    Button,
    copyToClipboard,
    user,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">
          Payment Integration
        </h2>
        <p className="text-slate-600">
          Configure payment methods to accept payments from your customers.
        </p>
      </div>

      {/* Payment Method Selection */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {paymentMethods.map((method) => {
          const Icon = method.icon;
          const isSelected = selectedMethod === method.id;
          const isAvailable = method.available;

          return (
            <div
              key={method.id}
              className={`relative p-6 rounded-xl border-2 transition-all cursor-pointer ${
                isSelected
                  ? "border-blue-500 bg-blue-50"
                  : isAvailable
                  ? "border-slate-200 bg-white hover:border-blue-300"
                  : "border-slate-200 bg-slate-50 opacity-50 cursor-not-allowed"
              }`}
              onClick={() => isAvailable && setSelectedMethod(method.id)}
            >
              {/* Recommended badge */}
              {method.recommended && (
                <div className="absolute -top-2 -right-2">
                  <div className="bg-yellow-400 text-yellow-900 text-xs font-bold px-2 py-1 rounded-full">
                    Recommended
                  </div>
                </div>
              )}

              <div className="flex items-start space-x-4">
                <div
                  className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                    method.color === "green"
                      ? "bg-green-100"
                      : method.color === "blue"
                      ? "bg-blue-100"
                      : method.color === "purple"
                      ? "bg-purple-100"
                      : "bg-slate-100"
                  }`}
                >
                  <Icon
                    className={`w-6 h-6 ${
                      method.color === "green"
                        ? "text-green-600"
                        : method.color === "blue"
                        ? "text-blue-600"
                        : method.color === "purple"
                        ? "text-purple-600"
                        : "text-slate-600"
                    }`}
                  />
                </div>

                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-slate-900">
                      {method.name}
                    </h3>
                    {isSelected && (
                      <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                    )}
                  </div>
                  <p className="text-sm text-slate-600 mt-1">
                    {method.description}
                  </p>

                  {!isAvailable && (
                    <div className="flex items-center space-x-2 mt-2 text-amber-600">
                      <AlertCircle className="w-4 h-4" />
                      <span className="text-sm">Only available in Kenya</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Configuration Panel */}
      <div className="bg-white rounded-xl border border-slate-200 p-8">
        {selectedMethod === "mpesa-api" && (
          <MpesaApiConfig
            config={paymentConfigs["mpesa-api"]}
            updateConfig={(updates) => updateConfig("mpesa-api", updates)}
            {...configProps}
          />
        )}

        {selectedMethod === "mpesa-sms" && (
          <MpesaSmsConfig
            config={paymentConfigs["mpesa-sms"]}
            updateConfig={(updates) => updateConfig("mpesa-sms", updates)}
            {...configProps}
          />
        )}

        {selectedMethod === "stripe" && (
          <StripeConfig
            config={paymentConfigs.stripe}
            updateConfig={(updates) => updateConfig("stripe", updates)}
            {...configProps}
          />
        )}

        {selectedMethod === "paypal" && (
          <PaypalConfig
            config={paymentConfigs.paypal}
            updateConfig={(updates) => updateConfig("paypal", updates)}
            {...configProps}
          />
        )}
      </div>
    </div>
  );
}
