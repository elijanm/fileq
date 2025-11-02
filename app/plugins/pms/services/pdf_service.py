import os
import requests
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime
from urllib.parse import quote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "..", "templates","pdf")
TEMPLATE_DIR = os.path.abspath(TEMPLATE_DIR)
MEDIA_DIR = "media"

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"])
)

BRAND = {
    "logo": f"{TEMPLATE_DIR}/logo.png",
    "company": "Cecil Homes",
    "watermark": f"{TEMPLATE_DIR}/watermark.png",
    "color": "#00a86b",
    "signature": "Authorized Manager",
}

async def generate_pdf(template_name: str, context: dict, prefix="doc_"):
    """Generate branded PDF with optional water usage graph"""
    os.makedirs(MEDIA_DIR, exist_ok=True)
    template = env.get_template(template_name)

    # Generate chart if data provided
    if "water_data" in context:
        context["water_chart"] = await generate_water_chart(context["water_data"])

    context["brand"] = BRAND
    html = template.render(**context)
    file_path = f"{MEDIA_DIR}/{prefix}{int(datetime.now().timestamp())}.pdf"
    HTML(string=html, base_url=".").write_pdf(file_path)
    return file_path


async def generate_water_chart(water_data: dict):
    """Create a monthly bar chart for water usage using QuickChart.io"""
    months = list(water_data.keys())
    values = list(water_data.values())

    chart_config = {
        "type": "bar",
        "data": {
            "labels": months,
            "datasets": [{
                "label": "Water Usage (m³)",
                "backgroundColor": BRAND["color"],
                "data": values
            }]
        },
        "options": {
            "plugins": {"legend": {"display": False}},
            "scales": {"y": {"beginAtZero": True}}
        }
    }

    config_encoded = quote(str(chart_config))
    chart_url = f"https://quickchart.io/chart?c={config_encoded}&backgroundColor=white&width=400&height=200"
    out_path = f"{MEDIA_DIR}/water_chart_{int(datetime.now().timestamp())}.png"

    # download chart image
    resp = requests.get(chart_url)
    if resp.status_code == 200:
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return out_path
    return None
