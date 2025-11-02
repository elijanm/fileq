// components/PricingSection.jsx
import React, { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    Check, X, Users, Crown, Building2, Sparkles, Zap, Shield,
    Star, ArrowRight, Headphones, Globe, Lock
} from "lucide-react";

export default function PricingSection() {
    const [billingCycle, setBillingCycle] = useState('monthly');
    const [selectedPlan, setSelectedPlan] = useState(null);

    const plans = [
        {
            id: 'free',
            name: "Free",
            icon: Users,
            price: { monthly: 0, yearly: 0 },
            description: "Perfect for personal use",
            popular: false,
            gradient: "from-slate-100 to-slate-200",
            textColor: "text-slate-900",
            borderColor: "border-slate-200",
            features: [
                "Files expire after 3 days",
                "3GB max file size",
                "Basic tools access",
                "Community support",
                "5 files per month",
                "Standard processing speed",
                "Basic file formats supported"
            ],
            limitations: [
                "Limited file formats",
                "No API access",
                "Basic security features",
                "No priority support"
            ],
            cta: "Get Started Free",
            badge: null,
            highlights: ["Great for trying FileQ", "No credit card required"]
        },
        {
            id: 'premium',
            name: "Premium",
            icon: Crown,
            price: { monthly: 9, yearly: 90 },
            description: "For professionals & creators",
            popular: true,
            gradient: "from-blue-500 to-cyan-500",
            textColor: "text-white",
            borderColor: "border-blue-500",
            features: [
                "Files stored for 12+ months",
                "Unlimited file size",
                "Access to all premium tools",
                "Priority support via email",
                "API access & CLI tools",
                "1000 files per month",
                "Advanced file processing",
                "Priority processing queue",
                "Advanced security features",
                "Custom file expiration dates"
            ],
            limitations: [],
            cta: "Upgrade to Premium",
            badge: "Most Popular",
            highlights: ["Best value for individuals", "Full API access included"]
        },
        {
            id: 'enterprise',
            name: "Enterprise",
            icon: Building2,
            price: { monthly: 49, yearly: 490 },
            description: "For teams & businesses",
            popular: false,
            gradient: "from-purple-500 to-indigo-500",
            textColor: "text-white",
            borderColor: "border-purple-500",
            features: [
                "Everything in Premium",
                "Unlimited file processing",
                "Team workspaces & collaboration",
                "SSO integration (SAML, OAuth)",
                "Audit logs & compliance",
                "24/7 dedicated support",
                "Custom integrations",
                "Advanced analytics & reporting",
                "White-label options",
                "99.9% SLA guarantee",
                "Priority feature requests"
            ],
            limitations: [],
            cta: "Start Enterprise Trial",
            badge: "Best for Teams",
            highlights: ["Advanced team features", "Enterprise-grade security"]
        },
        {
            id: 'custom',
            name: "Custom",
            icon: Sparkles,
            price: { monthly: "Custom", yearly: "Custom" },
            description: "Tailored for your needs",
            popular: false,
            gradient: "from-orange-500 to-red-500",
            textColor: "text-white",
            borderColor: "border-orange-500",
            features: [
                "Everything in Enterprise",
                "Custom file processing workflows",
                "Dedicated cloud infrastructure",
                "On-premise deployment options",
                "Custom SLA agreements",
                "Dedicated account manager",
                "Custom API development",
                "Advanced compliance (HIPAA, SOX)",
                "Multi-region deployment",
                "Priority feature development",
                "Custom integrations & plugins",
                "Dedicated training & onboarding"
            ],
            limitations: [],
            cta: "Contact Sales",
            badge: "Enterprise+",
            highlights: ["Fully customizable", "Dedicated infrastructure"]
        }
    ];

    const faqs = [
        {
            question: "Can I change plans anytime?",
            answer: "Yes, you can upgrade or downgrade your plan at any time. Changes take effect immediately, and we'll prorate any charges. Downgrades will take effect at the end of your current billing cycle."
        },
        {
            question: "What payment methods do you accept?",
            answer: "We accept all major credit cards (Visa, MasterCard, American Express), PayPal, and bank transfers for enterprise plans. All transactions are secure and encrypted with industry-standard SSL."
        },
        {
            question: "Is there a free trial for paid plans?",
            answer: "Yes, all paid plans come with a 14-day free trial with full access to all features. No credit card required to start, and you can cancel anytime during the trial period."
        },
        {
            question: "Do you offer refunds?",
            answer: "We offer a 30-day money-back guarantee for all paid plans. If you're not satisfied with FileQ, we'll provide a full refund within 30 days of your initial purchase."
        },
        {
            question: "What's included in the API access?",
            answer: "API access includes full REST API with 10,000+ requests per minute, webhooks for real-time notifications, SDKs for popular languages, comprehensive documentation, and priority technical support."
        },
        {
            question: "How does file storage work?",
            answer: "Free plans store files for 3 days, Premium and Enterprise plans store files for 12+ months with customizable retention policies. You have full control over file expiration and can extend storage as needed."
        },
        {
            question: "Is my data secure?",
            answer: "Absolutely. We use bank-grade encryption, are SOC 2 Type II certified, GDPR compliant, and regularly undergo security audits. Your files are encrypted in transit and at rest."
        },
        {
            question: "What happens if I exceed my plan limits?",
            answer: "We'll notify you when you're approaching your limits. For file count overages, you can upgrade your plan or purchase additional capacity. Processing continues normally with a small overage fee applied."
        }
    ];

    const addOns = [
        {
            name: "Additional Storage",
            description: "Extra long-term storage for your files beyond standard retention",
            price: "$5/month per 100GB",
            icon: Zap,
            popular: true
        },
        {
            name: "Priority Processing",
            description: "Jump to the front of the processing queue for faster results",
            price: "$10/month",
            icon: Zap,
            popular: false
        },
        {
            name: "Advanced Analytics",
            description: "Detailed insights, usage analytics, and custom reporting",
            price: "$15/month",
            icon: Zap,
            popular: true
        },
        {
            name: "Custom Branding",
            description: "White-label FileQ with your company branding and domain",
            price: "$25/month",
            icon: Zap,
            popular: false
        },
        {
            name: "Dedicated Support",
            description: "Private Slack channel with our engineering team",
            price: "$100/month",
            icon: Headphones,
            popular: false
        },
        {
            name: "Custom Integrations",
            description: "Built-to-order integrations with your existing tools",
            price: "Starting at $500/month",
            icon: Globe,
            popular: false
        }
    ];

    const testimonials = [
        {
            name: "Sarah Chen",
            role: "Product Designer",
            company: "TechCorp",
            content: "FileQ has transformed our design workflow. The batch processing alone saves us 10+ hours per week.",
            rating: 5
        },
        {
            name: "Marcus Johnson",
            role: "CTO",
            company: "StartupXYZ",
            content: "The API integration was seamless. Our customers love the fast file processing speeds.",
            rating: 5
        },
        {
            name: "Lisa Rodriguez",
            role: "Operations Manager",
            company: "Enterprise Inc",
            content: "Enterprise features and support are outstanding. FileQ scales with our growing business needs.",
            rating: 5
        }
    ];

    const handlePlanSelect = (planId) => {
        setSelectedPlan(planId);
        // In a real app, this would trigger the checkout process
        console.log(`Selected plan: ${planId}`);
    };

    return (
        <section id="pricing" className="bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 py-24">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                {/* Header */}
                <div className="text-center mb-16">
                    <h2 className="text-5xl font-bold text-white mb-6">
                        Simple, Transparent Pricing
                    </h2>
                    <p className="text-xl text-slate-300 mb-8 max-w-3xl mx-auto">
                        Choose the plan that fits your workflow. All plans include our core features
                        with no hidden fees or surprise charges. Start with our free tier and scale as you grow.
                    </p>

                    {/* Billing Toggle */}
                    <div className="inline-flex items-center bg-slate-800 rounded-xl p-1 shadow-lg border border-slate-700">
                        <button
                            onClick={() => setBillingCycle('monthly')}
                            className={`px-6 py-3 rounded-lg text-sm font-medium transition-all duration-300 ${billingCycle === 'monthly'
                                    ? 'bg-blue-600 text-white shadow-md transform scale-105'
                                    : 'text-slate-300 hover:text-white'
                                }`}
                        >
                            Monthly
                        </button>
                        <button
                            onClick={() => setBillingCycle('yearly')}
                            className={`px-6 py-3 rounded-lg text-sm font-medium transition-all duration-300 relative ${billingCycle === 'yearly'
                                    ? 'bg-blue-600 text-white shadow-md transform scale-105'
                                    : 'text-slate-300 hover:text-white'
                                }`}
                        >
                            Yearly
                            <span className="absolute -top-2 -right-2 bg-green-500 text-white text-xs px-2 py-1 rounded-full font-bold animate-pulse">
                                Save 17%
                            </span>
                        </button>
                    </div>
                </div>

                {/* Pricing Cards */}
                <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mb-20">
                    {plans.map((plan, index) => {
                        const IconComponent = plan.icon;
                        const isYearly = billingCycle === 'yearly';
                        const monthlyPrice = typeof plan.price.monthly === 'number' ? plan.price.monthly : 0;
                        const yearlyPrice = typeof plan.price.yearly === 'number' ? plan.price.yearly : 0;
                        const savings = isYearly && monthlyPrice > 0 ? (monthlyPrice * 12) - yearlyPrice : 0;

                        return (
                            <Card
                                key={index}
                                className={`relative border-2 transition-all duration-500 hover:scale-105 group cursor-pointer ${plan.popular
                                        ? 'border-blue-500 shadow-2xl scale-105 ring-4 ring-blue-500/20'
                                        : `${plan.borderColor} hover:border-opacity-80 shadow-xl hover:shadow-2xl`
                                    } bg-slate-800/60 backdrop-blur-sm overflow-hidden ${selectedPlan === plan.id ? 'ring-4 ring-blue-400/50' : ''
                                    }`}
                                onClick={() => handlePlanSelect(plan.id)}
                            >
                                {/* Popular Badge */}
                                {plan.badge && (
                                    <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 z-10">
                                        <div className={`px-6 py-2 rounded-full text-sm font-bold shadow-lg ${plan.popular
                                                ? 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white'
                                                : 'bg-gradient-to-r from-purple-500 to-indigo-500 text-white'
                                            }`}>
                                            {plan.badge}
                                        </div>
                                    </div>
                                )}

                                {/* Gradient Background Effect */}
                                <div className={`absolute inset-0 bg-gradient-to-br ${plan.gradient} opacity-0 group-hover:opacity-10 transition-opacity duration-500`}></div>

                                <CardHeader className="pb-6 relative z-10">
                                    <div className="flex items-center justify-between mb-4">
                                        <div className="flex items-center space-x-3">
                                            <div className={`w-12 h-12 bg-gradient-to-br ${plan.gradient} rounded-xl flex items-center justify-center shadow-lg`}>
                                                <IconComponent className="w-6 h-6 text-white" />
                                            </div>
                                            <div>
                                                <CardTitle className="text-2xl text-white">{plan.name}</CardTitle>
                                                <p className="text-slate-400 text-sm">{plan.description}</p>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Price */}
                                    <div className="mb-4">
                                        <div className="flex items-baseline">
                                            <span className="text-4xl font-bold text-white">
                                                {typeof plan.price[billingCycle] === 'number' ?
                                                    (plan.price[billingCycle] === 0 ? 'Free' : `${plan.price[billingCycle]}`) :
                                                    plan.price[billingCycle]
                                                }
                                            </span>
                                            {typeof plan.price[billingCycle] === 'number' && plan.price[billingCycle] > 0 && (
                                                <span className="text-lg text-slate-400 ml-1 font-normal">
                                                    /{billingCycle === 'monthly' ? 'month' : 'year'}
                                                </span>
                                            )}
                                        </div>
                                        {savings > 0 && (
                                            <div className="text-sm text-green-400 font-medium mt-1">
                                                💰 Save ${savings} per year
                                            </div>
                                        )}
                                    </div>

                                    {/* Highlights */}
                                    {plan.highlights && (
                                        <div className="mb-4">
                                            {plan.highlights.map((highlight, idx) => (
                                                <div key={idx} className="flex items-center text-blue-300 text-sm mb-1">
                                                    <Star className="w-3 h-3 mr-2 fill-current" />
                                                    {highlight}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </CardHeader>

                                <CardContent className="space-y-6 relative z-10">
                                    {/* Features List */}
                                    <div className="space-y-3 max-h-80 overflow-y-auto custom-scrollbar">
                                        {plan.features.map((feature, idx) => (
                                            <div key={idx} className="flex items-start space-x-3">
                                                <div className="bg-green-500/20 rounded-full p-1 mt-0.5 flex-shrink-0">
                                                    <Check className="w-3 h-3 text-green-400" />
                                                </div>
                                                <span className="text-slate-300 text-sm leading-relaxed">{feature}</span>
                                            </div>
                                        ))}
                                        {plan.limitations.map((limitation, idx) => (
                                            <div key={idx} className="flex items-start space-x-3">
                                                <div className="bg-red-500/20 rounded-full p-1 mt-0.5 flex-shrink-0">
                                                    <X className="w-3 h-3 text-red-400" />
                                                </div>
                                                <span className="text-slate-400 text-sm leading-relaxed">{limitation}</span>
                                            </div>
                                        ))}
                                    </div>

                                    {/* CTA Button */}
                                    <Button
                                        className={`w-full transition-all duration-300 font-semibold ${plan.popular
                                                ? 'bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white shadow-lg hover:shadow-xl'
                                                : plan.name === 'Free'
                                                    ? 'bg-slate-700 hover:bg-slate-600 text-white'
                                                    : 'bg-gradient-to-r from-purple-500 to-indigo-500 hover:from-purple-600 hover:to-indigo-600 text-white'
                                            } hover:scale-105 transform group-hover:shadow-2xl`}
                                        size="lg"
                                    >
                                        {plan.cta}
                                        <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                                    </Button>

                                    {/* Additional Info */}
                                    <div className="pt-4 border-t border-slate-700 text-center">
                                        <p className="text-slate-400 text-xs">
                                            {plan.name === 'Free' ? 'No credit card required' :
                                                plan.name === 'Custom' ? 'Custom pricing & terms' :
                                                    '14-day free trial • Cancel anytime'}
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>

                {/* Customer Testimonials */}
                <div className="mb-20">
                    <h3 className="text-3xl font-bold text-white text-center mb-12">
                        Loved by 10,000+ customers worldwide
                    </h3>
                    <div className="grid md:grid-cols-3 gap-8">
                        {testimonials.map((testimonial, index) => (
                            <div key={index} className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700">
                                <div className="flex items-center mb-4">
                                    {[...Array(testimonial.rating)].map((_, i) => (
                                        <Star key={i} className="w-4 h-4 text-yellow-400 fill-current" />
                                    ))}
                                </div>
                                <p className="text-slate-300 mb-4 italic">"{testimonial.content}"</p>
                                <div className="flex items-center">
                                    <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center mr-3">
                                        <span className="text-white font-semibold text-sm">
                                            {testimonial.name.split(' ').map(n => n[0]).join('')}
                                        </span>
                                    </div>
                                    <div>
                                        <div className="text-white font-medium">{testimonial.name}</div>
                                        <div className="text-slate-400 text-sm">{testimonial.role} at {testimonial.company}</div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Add-ons Section */}
                <div className="mb-20">
                    <div className="text-center mb-12">
                        <h3 className="text-3xl font-bold text-white mb-4">Popular Add-ons</h3>
                        <p className="text-slate-300 max-w-2xl mx-auto">
                            Enhance your plan with these optional features. All add-ons can be added
                            to any paid plan and are billed monthly.
                        </p>
                    </div>

                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {addOns.map((addon, index) => {
                            const IconComponent = addon.icon;
                            return (
                                <div
                                    key={index}
                                    className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700 hover:border-slate-600 transition-all duration-300 hover:scale-105 group"
                                >
                                    <div className="flex items-start justify-between mb-4">
                                        <div className="flex items-center">
                                            <div className="bg-blue-600/20 rounded-lg p-2 mr-3">
                                                <IconComponent className="w-5 h-5 text-blue-400" />
                                            </div>
                                            <h4 className="font-semibold text-white">{addon.name}</h4>
                                        </div>
                                        {addon.popular && (
                                            <span className="bg-green-500 text-white text-xs px-2 py-1 rounded-full font-medium">
                                                Popular
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-slate-400 text-sm mb-4 leading-relaxed">{addon.description}</p>
                                    <div className="flex items-center justify-between">
                                        <p className="text-blue-400 font-semibold">{addon.price}</p>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            className="border-blue-500 text-blue-400 hover:bg-blue-500 hover:text-white transition-colors"
                                        >
                                            Add
                                        </Button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* FAQ Section */}
                <div className="mb-16">
                    <h3 className="text-3xl font-bold text-white mb-12 text-center">Frequently Asked Questions</h3>
                    <div className="grid md:grid-cols-2 gap-8 max-w-6xl mx-auto">
                        {faqs.map((faq, index) => (
                            <div key={index} className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700 hover:border-slate-600 transition-colors">
                                <h4 className="text-lg font-semibold text-white mb-3">{faq.question}</h4>
                                <p className="text-slate-400 leading-relaxed">{faq.answer}</p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Trust Indicators */}
                <div className="text-center">
                    <h3 className="text-2xl font-bold text-white mb-8">Enterprise-grade security and reliability</h3>
                    <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
                        <div className="flex flex-col items-center group">
                            <div className="bg-green-500/20 rounded-full p-4 mb-4 group-hover:scale-110 transition-transform">
                                <Shield className="w-8 h-8 text-green-400" />
                            </div>
                            <h4 className="text-white font-semibold mb-2">SOC 2 Certified</h4>
                            <p className="text-slate-400 text-sm text-center">
                                SOC 2 Type II compliant with bank-grade encryption and security protocols
                            </p>
                        </div>
                        <div className="flex flex-col items-center group">
                            <div className="bg-blue-500/20 rounded-full p-4 mb-4 group-hover:scale-110 transition-transform">
                                <Users className="w-8 h-8 text-blue-400" />
                            </div>
                            <h4 className="text-white font-semibold mb-2">10,000+ Companies</h4>
                            <p className="text-slate-400 text-sm text-center">
                                Trusted by startups to Fortune 500 companies worldwide
                            </p>
                        </div>
                        <div className="flex flex-col items-center group">
                            <div className="bg-purple-500/20 rounded-full p-4 mb-4 group-hover:scale-110 transition-transform">
                                <Globe className="w-8 h-8 text-purple-400" />
                            </div>
                            <h4 className="text-white font-semibold mb-2">99.9% Uptime</h4>
                            <p className="text-slate-400 text-sm text-center">
                                Reliable service with guaranteed uptime and global infrastructure
                            </p>
                        </div>
                    </div>

                    {/* Final CTA */}
                    <div className="mt-16 text-center">
                        <h3 className="text-2xl font-bold text-white mb-4">
                            Ready to transform your file workflow?
                        </h3>
                        <p className="text-slate-300 mb-8 max-w-2xl mx-auto">
                            Join thousands of satisfied customers who have streamlined their file processing with FileQ.
                            Start your free trial today – no credit card required.
                        </p>
                        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                            <Button
                                size="lg"
                                className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white font-semibold px-8 py-4 shadow-xl hover:shadow-2xl transition-all transform hover:scale-105"
                            >
                                Start Free Trial
                                <ArrowRight className="w-5 h-5 ml-2" />
                            </Button>
                            <Button
                                size="lg"
                                variant="outline"
                                className="border-slate-400 text-slate-300 hover:bg-white hover:text-slate-900 px-8 py-4 font-semibold transition-all"
                            >
                                Talk to Sales
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            <style jsx>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: rgba(51, 65, 85, 0.3);
          border-radius: 2px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(59, 130, 246, 0.5);
          border-radius: 2px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(59, 130, 246, 0.7);
        }
      `}</style>
        </section>
    );
}