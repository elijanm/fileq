import React from "react";
import { Smartphone, Info, Download, Copy, ExternalLink } from "lucide-react";

export default function MpesaSmsConfig({
  config,
  updateConfig,
  Button,
  copyToClipboard,
  user,
}) {
  const webhookUrl = `https://api.fileq.com/webhook/mpesa-sms/${
    user?.id || "your-user-id"
  }`;

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
          <Smartphone className="w-5 h-5 text-green-600" />
        </div>
        <div>
          <h3 className="text-xl font-semibold text-slate-900">
            M-Pesa SMS Verification
          </h3>
          <p className="text-sm text-slate-600">
            Real-time payment verification using MpesaSync App
          </p>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start space-x-3">
          <Info className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="font-medium text-blue-900 mb-2">How it Works</h4>
            <p className="text-sm text-blue-800">
              MpesaSync App reads M-Pesa SMS messages on your Android device and
              sends payment confirmations to your system in real-time. No API
              credentials required from Safaricom.
            </p>
          </div>
        </div>
      </div>

      {/* Setup Steps */}
      <div className="space-y-4">
        <h4 className="font-medium text-slate-900">Setup Instructions:</h4>

        <div className="space-y-4">
          {[
            {
              step: 1,
              title: "Download MpesaSync App",
              description:
                "Install the MpesaSync app on an Android device that receives M-Pesa SMS notifications.",
              action: (
                <Button size="sm" className="mt-2">
                  <Download className="w-4 h-4 mr-2" />
                  Download APK
                </Button>
              ),
            },
            {
              step: 2,
              title: "Configure Webhook URL",
              description:
                "Add this webhook URL to your MpesaSync app settings:",
              action: (
                <div className="mt-2 bg-slate-100 rounded-lg p-3 flex items-center justify-between">
                  <code className="text-sm font-mono text-slate-700 break-all">
                    {webhookUrl}
                  </code>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(webhookUrl)}
                  >
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
              ),
            },
            {
              step: 3,
              title: "Grant Permissions",
              description:
                "Allow the app to read SMS messages and access the internet for webhook delivery.",
            },
            {
              step: 4,
              title: "Test Integration",
              description:
                "Send a test M-Pesa payment to verify the integration is working correctly.",
            },
          ].map((item) => (
            <div key={item.step} className="flex items-start space-x-3">
              <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-sm font-medium text-blue-600">
                  {item.step}
                </span>
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-900">
                  {item.title}
                </p>
                <p className="text-sm text-slate-600 mt-1">
                  {item.description}
                </p>
                {item.action}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center space-x-4 pt-4 border-t border-slate-200">
        <Button onClick={() => updateConfig({ enabled: true })}>
          Enable SMS Integration
        </Button>
        <Button variant="outline">
          <ExternalLink className="w-4 h-4 mr-2" />
          Setup Guide
        </Button>
      </div>
    </div>
  );
}
