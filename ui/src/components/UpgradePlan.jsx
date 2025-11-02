import React from "react";
import { Crown, Check } from "lucide-react";

export default function UpgradePlan() {
  // Button component
  const Button = ({
    children,
    onClick,
    variant = "default",
    size = "default",
    className,
    disabled,
    ...props
  }) => {
    const baseClasses =
      "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
    const variants = {
      default: "bg-blue-600 text-white hover:bg-blue-700",
      outline:
        "border border-slate-200 bg-white hover:bg-slate-100 hover:text-slate-900",
      ghost: "hover:bg-slate-100",
    };
    const sizes = {
      default: "h-10 py-2 px-4",
      sm: "h-9 px-3 text-sm",
      lg: "h-11 px-8",
    };

    return (
      <button
        className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${
          className || ""
        }`}
        onClick={onClick}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    );
  };

  // Card component
  const Card = ({ children, className }) => (
    <div className={`bg-white rounded-lg shadow border ${className || ""}`}>
      {children}
    </div>
  );

  const CardContent = ({ children, className }) => (
    <div className={`p-6 ${className || ""}`}>{children}</div>
  );

  const plans = [
    {
      name: "Free",
      price: 0,
      period: "month",
      features: ["5GB Storage", "100 Files/month", "Basic Support"],
      current: true,
    },
    {
      name: "Pro",
      price: 9.99,
      period: "month",
      features: [
        "100GB Storage",
        "Unlimited Files",
        "Priority Support",
        "Advanced Analytics",
      ],
      popular: true,
    },
    {
      name: "Team",
      price: 19.99,
      period: "month",
      features: [
        "500GB Storage",
        "Team Collaboration",
        "24/7 Support",
        "Admin Controls",
      ],
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <main className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-slate-900 mb-4">
            Choose Your Plan
          </h1>
          <p className="text-xl text-slate-600 max-w-3xl mx-auto">
            Upgrade your FileQ experience with more storage, features, and
            support.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {plans.map((plan) => (
            <Card
              key={plan.name}
              className={`relative border-2 transition-all hover:scale-105 ${
                plan.popular
                  ? "border-blue-500 shadow-xl"
                  : plan.current
                  ? "border-green-500"
                  : "border-slate-200"
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                  <div className="bg-gradient-to-r from-blue-500 to-cyan-500 text-white px-4 py-1 rounded-full text-sm font-medium">
                    Most Popular
                  </div>
                </div>
              )}

              {plan.current && (
                <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                  <div className="bg-green-500 text-white px-4 py-1 rounded-full text-sm font-medium">
                    Current Plan
                  </div>
                </div>
              )}

              <CardContent className="p-8 text-center">
                <h3 className="text-2xl font-bold text-slate-900 mb-2">
                  {plan.name}
                </h3>
                <div className="mb-6">
                  <span className="text-4xl font-bold text-slate-900">
                    ${plan.price}
                  </span>
                  <span className="text-slate-600">/{plan.period}</span>
                </div>

                <ul className="space-y-3 mb-8">
                  {plan.features.map((feature, index) => (
                    <li
                      key={index}
                      className="flex items-center justify-center space-x-2"
                    >
                      <Check className="w-5 h-5 text-green-500 flex-shrink-0" />
                      <span className="text-slate-600">{feature}</span>
                    </li>
                  ))}
                </ul>

                <Button
                  className={`w-full ${
                    plan.popular
                      ? "bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white"
                      : plan.current
                      ? "bg-green-500 hover:bg-green-600 text-white"
                      : ""
                  }`}
                  variant={plan.popular || plan.current ? "default" : "outline"}
                  disabled={plan.current}
                >
                  {plan.current ? "Current Plan" : `Choose ${plan.name}`}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* FAQ Section */}
        <div className="mt-16 max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold text-slate-900 text-center mb-8">
            Frequently Asked Questions
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg p-6 shadow">
              <h3 className="font-semibold text-slate-900 mb-3">
                Can I change my plan later?
              </h3>
              <p className="text-slate-600 text-sm">
                Yes! You can upgrade or downgrade your plan at any time. Changes
                will be reflected in your next billing cycle.
              </p>
            </div>

            <div className="bg-white rounded-lg p-6 shadow">
              <h3 className="font-semibold text-slate-900 mb-3">
                Is there a free trial for Pro plans?
              </h3>
              <p className="text-slate-600 text-sm">
                Yes, we offer a 14-day free trial for both Pro and Team plans.
                No credit card required to start your trial.
              </p>
            </div>

            <div className="bg-white rounded-lg p-6 shadow">
              <h3 className="font-semibold text-slate-900 mb-3">
                What payment methods do you accept?
              </h3>
              <p className="text-slate-600 text-sm">
                We accept all major credit cards, PayPal, and bank transfers for
                annual plans.
              </p>
            </div>

            <div className="bg-white rounded-lg p-6 shadow">
              <h3 className="font-semibold text-slate-900 mb-3">
                Is my data secure?
              </h3>
              <p className="text-slate-600 text-sm">
                Absolutely! All your files are encrypted in transit and at rest.
                We use enterprise-grade security measures.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
