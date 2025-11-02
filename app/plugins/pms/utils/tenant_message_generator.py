import os,re
import requests
from jinja2 import Template


def extract_sections(message_text: str) -> dict[str, str]:
    """
    Extracts SMS, Email, and other labeled sections from model output.
    Handles markdown (**SMS:**), plain (SMS:), and emoji headers.
    Works for both Qwen and DeepSeek style outputs.
    """
    sections = {}
    current = None
    buffer = []

    for line in message_text.splitlines():
        stripped = line.strip()

        # Match headers like "**SMS:**", "SMS:", "📱 SMS:", etc.
        match = re.match(
            r"^[\*\s_]*[📱📧]*\s*([A-Za-z][A-Za-z'&\s]+?)\s*:\s*\**\s*(.*)$",
            stripped,
            re.IGNORECASE,
        )

        if match:
            # Save previous section if exists
            if current and buffer:
                sections[current] = "\n".join(buffer).strip()

            current = match.group(1).strip().title()  # e.g., Sms → SMS
            inline_text = match.group(2).strip()
            buffer = [inline_text] if inline_text else []
            continue

        # Skip markdown separators
        if stripped == "---":
            continue

        # Add continuation lines
        if current:
            buffer.append(stripped)

    # Save last section
    if current and buffer:
        sections[current] = "\n".join(buffer).strip()

    return sections
class TenantMessageGenerator:
    """
    Generates personalized tenant messages (SMS + Email)
    using DeepSeek API or a compatible local inference endpoint.
    """

    BASE_URL = os.getenv("BASE_URL", "http://95.110.228.29:8201/v1")
    MODEL = os.getenv("MODEL", "qwen2.5:7b")
    API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY", "sk-no-key-needed-for-local")

    def __init__(self):
        self.endpoint = f"{self.BASE_URL}/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json",
        }

    def _build_prompt(self, tenant_data: dict) -> str:
        """
        Renders the DeepSeek prompt using tenant financial/lease data.
        """

        template_text = """
            You are a professional assistant for a property management company.
            Your task is to write clear, natural, and friendly tenant messages
            that encourage timely payments, renewals, and good relationships.

            You should sound human, helpful, and professional — not robotic.

            TONE RULES:
            - 🟢 Reliable Tenants (on_time_rate > 70% and risk_level == "LOW"):
            Warm and appreciative tone. Reinforce consistency and reliability.
            Example: “Thanks for keeping up with your payments — we appreciate your reliability!”
            - 🟡 At-Risk Tenants (40–70% or risk_level == "MEDIUM"):
            Supportive tone. Recognize effort but gently encourage improvement.
            Example: “Thanks for your effort so far — let’s stay consistent this month!”
            - 🔴 Delinquent Tenants (on_time_rate < 40% or risk_level == "HIGH"):
            Calm but firm tone. Encourage payment while maintaining professionalism.
            Example: “We’ve noticed some delayed payments — please clear your dues soon to avoid late fees.”

            LEASE CONTEXT RULES:
            - If move_out_notice_given > 0:
            Focus on positive transitioning and gratitude.
            Example: “Thank you for being with us — we wish you a smooth move-out process.”
            - If days_to_lease_expiry < 90 and move_out_notice_given == 0:
            Encourage renewal in a warm, professional way.
            Example: “Your lease ends soon — we’d love to have you renew for another term.”
            - Otherwise:
            Focus on reliability, responsibility, and helpful guidance.
            - If avg_delay_days is increasing → encourage timely payment.
            - If tenure_in_month < 3 → welcoming tone (“we’re glad to have you with us”).
            - If avg_daily_utility_use is high → gentle conservation advice.
            - If outstanding_balance > 0 → include invoice context below.
            - Always close politely and positively.

            INVOICE CONTEXT (if outstanding_balance > 0):
            Include a short summary of unpaid invoices and total amount:
            - Invoice Number: {{invoice_no}}
            - Line Items:
            {% for item in line_items %}
            • {{item.name}} — KES {{item.amount}}
            {% endfor %}
            - Total Outstanding: KES {{outstanding_balance}}

            Mention the total and encourage payment clearly:
            Example: “Your current total balance is KES {{outstanding_balance}} (Invoice #{{invoice_no}}). Please clear it soon to stay current.”

            TENANT OVERVIEW:
            - Name: {{full_name}}
            - Property: {{property_name}} — {{unit_name}}
            - On-time Payment Rate: {{on_time_rate}}%
            - Collection Rate: {{collection_rate}}%
            - Outstanding Balance: KES {{outstanding_balance}}
            - Average Payment Delay: {{avg_delay_days}} days
            - Early Payment Score: {{early_payment_score}}
            - Reliability / Risk Level: {{risk_level}} ({{risk_score}} — lower is better)
            - Days to Lease Expiry: {{days_to_lease_expiry}}
            - Move-Out Notice Given: {{move_out_notice_given}} days
            - Tenure: {{tenure_in_month}} months
            - Average Daily Utility Use: {{avg_daily_utility_use}}
            - Internal Recommendation: {{recommendation}}

            INSTRUCTIONS:
            1. Analyze the tenant’s situation using tone + lease + invoice context.
            2. If invoices exist:
            - Mention the invoice number(s) and total due (KES {{outstanding_balance}}).
            - Refer to one or two key line items naturally (e.g., “for January rent and utilities”).
            3. If no balance is due:
            - Focus on appreciation, renewal, or general goodwill.
            4. Always end messages with the signature:
            “— {{property_name}} Management Team”
            5. Output two messages:
            - **SMS:** under 240 characters, concise and human.
            - **Email:** 2–4 sentences, slightly more detailed but still friendly.

            STRICT OUTPUT FORMAT:
            **SMS:** <text>
            **Email:** <text>
            """




        template = Template(template_text.strip())
        return template.render(**tenant_data)

    def generate_message(self, tenant_data: dict) -> dict:
        """
        Sends tenant data to DeepSeek model and returns SMS + Email versions.
        """
        prompt = self._build_prompt(tenant_data)

        payload = {
            "model": self.MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
            "max_tokens": 40000,
        }

        response = requests.post(self.endpoint, headers=self.headers, json=payload, timeout=60)

        if response.status_code != 200:
            raise RuntimeError(
                f"DeepSeek API error {response.status_code}: {response.text}"
            )

        result = response.json()
        import re
        message_text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        cleaned_content = re.sub(r"<think>.*?</think>", "", message_text, flags=re.DOTALL).strip()

        # Now safe to truncate or store
        message_text = cleaned_content[:40000]  # only if needed
        print(message_text)
        d = extract_sections(message_text)
        print(d)
        sms_text, email_text = d["Sms"], d["Email"]
        
        return {
            "sms": sms_text,
            "email": email_text,
            "raw": message_text,
        }


# ✅ Example usage
if __name__ == "__main__":
    tenant = {
        "full_name": "Margaret Wairimu",
        "property_name": "Ngong Road Residences",
        "unit_name": "Unit A-08",
        "on_time_rate": 70,
        "collection_rate": 1,
        "outstanding_balance": 100,
        "avg_delay_days": 16.67,
        "early_payment_score": 74.3,
        "risk_level": "LOW",
        "risk_score": 11.53,
        "days_to_lease_expiry": 360,
        "move_out_notice_given": 0,
        "invoice_no":"INV-2023-9",
        "line_items":[
            {"amount":80,"name":"Oct Rent"},
            {"amount":20,"name":"Oct Utility"},
        ],
        "tenure_in_month":10,
        "recommendation":"High average delay in payments – review late fee policy or enforce stricter follow-ups."
    }

    generator = TenantMessageGenerator()
    result = generator.generate_message(tenant)
    print("📱 SMS:", result["sms"])
    print("📧 Email:", result["email"])
