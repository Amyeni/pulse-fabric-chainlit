import json
import re

with open("domain_catalog.json", "r", encoding="utf-8") as f:
    domains = json.load(f)

request_text = "We want to re-analyze campaign performance data from 5 years ago"


def normalize(text):
    return re.sub(r"[^a-z0-9ğüşöçıİĞÜŞÖÇ ]", " ", str(text).lower())


DOMAIN_BOOST_RULES = {
    "Marketing": ["campaign", "campaigns", "marketing", "nps", "profitability", "promotion"],
    "Customer": ["customer id", "customer identity", "customer type", "tariff"],
    "Product & Service": ["tariff", "bundle", "pricing", "product", "service"],
    "Customer Service Performance": ["aht", "fcr", "call center", "service efficiency"],
    "Management Reporting": ["executive", "market share", "arpu", "kpi"],
    "Network Capacity & Performance Mgmt": ["network performance", "capacity"],
    "Digital Channel Performance": ["digital analytics", "heatmap", "page load"],
}


def score_domain(request, domain):
    request_n = normalize(request)

    searchable = normalize(
        f"{domain['domain_name']} "
        f"{domain['category']} "
        f"{domain['definition']} "
        f"{domain['sample_data']} "
        f"{domain['data_owner']} "
        f"{domain['related_sub_team']}"
    )

    request_terms = set(request_n.split())

    score = 0
    reasons = []

    for term in request_terms:
        if len(term) > 2 and term in searchable:
            score += 1
            reasons.append(f"keyword match: {term}")

    domain_name = domain["domain_name"]

    for boost_term in DOMAIN_BOOST_RULES.get(domain_name, []):
        if boost_term in request_n:
            score += 5
            reasons.append(f"domain boost: {boost_term}")

    if "campaign performance" in request_n and domain_name == "Marketing":
        score += 10
        reasons.append("strong phrase match: campaign performance")

    if "performance" in request_n and "performance" in searchable:
        score += 3
        reasons.append("performance match")

    return score, reasons


scored = []
for domain in domains:
    score, reasons = score_domain(request_text, domain)
    scored.append((score, domain, reasons))

scored.sort(key=lambda x: x[0], reverse=True)

print("TOP MATCHES")
for score, domain, reasons in scored[:5]:
    print(score, "-", domain["domain_name"], "|", domain["definition"])
    print("   reasons:", "; ".join(reasons[:5]))