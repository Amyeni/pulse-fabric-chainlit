import os
import json
import re
from dotenv import load_dotenv
import chainlit as cl
from openai import OpenAI

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "openrouter/free")
API_BASE = os.getenv("API_BASE", "https://openrouter.ai/api/v1")
API_KEY = os.getenv("API_KEY")

client = OpenAI(api_key=API_KEY, base_url=API_BASE)

AGENT_IMAGE_PATH = "public/agents.png"

AGENT_ICONS = {
    "Scout": "🦅",
    "Inspector": "🦉",
    "Strategist": "🐺",
    "Scribe": "🐙",
    "Conductor": "🐬",
    "Guardian": "🦏"
}

CUSTOMER_JOURNEYS = {
    "1": {
        "name": "KVKK / PII Risky Request",
        "sample": "We need a dataset including customer phone number, TCKN, location and package information for campaign targeting."
    },
    "2": {
        "name": "Expired Retention Data Request",
        "sample": "We want to re-analyze campaign performance data from 5 years ago."
    },
    "3": {
        "name": "Existing Data Discovery and Routing",
        "sample": "We want to understand which platform contains the data required for the customer segmentation report."
    }
}

REQUIRED_FIELDS = {
    "business_need": "Business need",
    "data_domain": "Data domain",
    "source_system": "Source system",
    "expected_output": "Expected output",
    "consumer": "Consumer",
    "frequency": "Frequency",
    "contains_pii": "Contains PII",
    "deadline": "Deadline"
}


def safe_json_loads(text):
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def get_missing_fields(data):
    missing = []
    for key in REQUIRED_FIELDS:
        value = data.get(key)
        if value in [None, "", "-", "Unknown", "unknown", "N/A", "n/a"]:
            missing.append(key)
    return missing


def load_rag_context():
    if not os.path.exists("rag_index.json"):
        return []
    with open("rag_index.json", "r", encoding="utf-8") as f:
        return json.load(f)


def rag_search(query, top_k=8):
    docs = load_rag_context()
    query_words = set(query.lower().replace(",", " ").replace(".", " ").split())

    scored = []
    for doc in docs:
        text = doc.get("text", "").lower()
        score = sum(1 for word in query_words if word in text)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def build_prompt(user_request, contexts, current_data=None):
    context_text = "\n\n".join(
        [
            f"[{i + 1}] {c.get('source', 'source')}:\n{c.get('text', '')}"
            for i, c in enumerate(contexts)
        ]
    )

    return f"""
You are Pulse Fabric, an AI-powered data governance and request maturation assistant.

Use the following enterprise context:
- Data governance guardrails
- Data domain catalog
- Data ownership information
- Retention and PII rules when available

User request:
{user_request}

Existing filled fields:
{json.dumps(current_data or {}, ensure_ascii=False, indent=2)}

RAG context:
{context_text}

Return ONLY valid JSON with this schema:

{{
  "business_need": "",
  "data_domain": "",
  "source_system": "",
  "expected_output": "",
  "consumer": "",
  "frequency": "",
  "contains_pii": "",
  "deadline": "",
  "request_maturity_score": 0,
  "priority_score": 0,
  "risk_level": "LOW / MEDIUM / HIGH",
  "guardian_decision": "Auto Approve / Needs Review / Escalate",
  "next_step": "",
  "agent_timeline": {{
    "Scout": "",
    "Inspector": "",
    "Strategist": "",
    "Scribe": "",
    "Conductor": "",
    "Guardian": ""
  }}
}}
"""


def ask_llm(user_request, contexts, current_data=None):
    prompt = build_prompt(user_request, contexts, current_data)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "You are a data governance assistant. Return only valid JSON. Do not add markdown."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    return safe_json_loads(response.choices[0].message.content)


def render_table(title, rows):
    md = f"\n## {title}\n\n| Field | Value | Agent |\n|---|---|---|\n"
    for field, value, agent in rows:
        md += f"| **{field}** | {value or '-'} | {agent} |\n"
    return md


def render_result(data, contexts, user_request):
    incoming_rows = [
        ("Initial Request", user_request, f"{AGENT_ICONS['Scout']} Scout"),
        ("Business Need", data.get("business_need"), f"{AGENT_ICONS['Scout']} Scout"),
        ("Data Domain", data.get("data_domain"), f"{AGENT_ICONS['Scout']} Scout"),
        ("Source System", data.get("source_system"), f"{AGENT_ICONS['Inspector']} Inspector"),
        ("Expected Output", data.get("expected_output"), f"{AGENT_ICONS['Scribe']} Scribe"),
        ("Consumer", data.get("consumer"), f"{AGENT_ICONS['Conductor']} Conductor"),
        ("Frequency", data.get("frequency"), f"{AGENT_ICONS['Inspector']} Inspector"),
        ("Contains PII", data.get("contains_pii"), f"{AGENT_ICONS['Guardian']} Guardian"),
        ("Deadline", data.get("deadline"), f"{AGENT_ICONS['Strategist']} Strategist"),
    ]

    control_rows = [
        ("Request Maturity Score", f"{data.get('request_maturity_score', '-')}/100", f"{AGENT_ICONS['Inspector']} Inspector"),
        ("Priority Score", f"{data.get('priority_score', '-')}/100", f"{AGENT_ICONS['Strategist']} Strategist"),
        ("Risk Level", data.get("risk_level"), f"{AGENT_ICONS['Guardian']} Guardian"),
        ("Guardian Decision", data.get("guardian_decision"), f"{AGENT_ICONS['Guardian']} Guardian"),
        ("Next Step", data.get("next_step"), f"{AGENT_ICONS['Conductor']} Conductor"),
    ]

    timeline = data.get("agent_timeline", {})
    timeline_rows = []
    for agent in ["Scout", "Inspector", "Strategist", "Scribe", "Conductor", "Guardian"]:
        timeline_rows.append(
            (
                f"{AGENT_ICONS.get(agent, '🤖')} {agent}",
                timeline.get(agent, "-"),
                "Assigned"
            )
        )

    md = ""
    md += render_table("📥 Incoming Request", incoming_rows)
    md += "\n---\n"
    md += render_table("📊 Control Tower", control_rows)
    md += "\n---\n"
    md += render_table("🤖 Agent Timeline", timeline_rows)

    sources = "\n".join(
        [f"- {c.get('source', 'source')}" for c in contexts[:5]]
    )

    md += f"\n---\n## 📚 RAG Sources Used\n{sources if sources else '-'}\n"
    return md


async def ask_next_missing_field():
    missing_fields = cl.user_session.get("missing_fields") or []
    missing_index = cl.user_session.get("missing_index") or 0

    if missing_index >= len(missing_fields):
        return False

    field = missing_fields[missing_index]

    await cl.Message(content=f"""
## ⚠️ Missing Field {missing_index + 1} of {len(missing_fields)}

🔎 **Inspector Agent**

**{REQUIRED_FIELDS[field]}?**
""").send()

    return True


@cl.on_chat_start
async def start():
    cl.user_session.set("request_data", None)
    cl.user_session.set("user_request", None)
    cl.user_session.set("contexts", None)
    cl.user_session.set("awaiting_missing_fields", False)
    cl.user_session.set("missing_fields", [])
    cl.user_session.set("missing_index", 0)
    cl.user_session.set("missing_answers", {})

    elements = []
    if os.path.exists(AGENT_IMAGE_PATH):
        elements.append(
            cl.Image(
                name="Pulse Fabric Agents",
                path=AGENT_IMAGE_PATH,
                display="inline"
            )
        )

    await cl.Message(
        content="""
# 🔴 Pulse Fabric MVP

**AI-powered Demand Governance & Request Maturation Demo**

## Select a Customer Journey

| No | Customer Journey |
|---|---|
| **1** | KVKK / PII Risky Request |
| **2** | Expired Retention Data Request |
| **3** | Existing Data Discovery and Routing |

Please type **1**, **2**, **3**, or write your own data request.
""",
        elements=elements
    ).send()


@cl.on_message
async def main(message: cl.Message):
    user_input = message.content.strip()

    awaiting_missing = cl.user_session.get("awaiting_missing_fields")
    current_data = cl.user_session.get("request_data")
    user_request = cl.user_session.get("user_request")
    contexts = cl.user_session.get("contexts")

    if awaiting_missing:
        missing_fields = cl.user_session.get("missing_fields") or []
        missing_index = cl.user_session.get("missing_index") or 0
        missing_answers = cl.user_session.get("missing_answers") or {}

        current_field = missing_fields[missing_index]
        missing_answers[current_field] = user_input

        cl.user_session.set("missing_answers", missing_answers)

        next_index = missing_index + 1
        cl.user_session.set("missing_index", next_index)

        if next_index < len(missing_fields):
            await ask_next_missing_field()
            return

        await cl.Message(
            content="🔄 All missing fields collected. Recalculating request maturity..."
        ).send()

        enriched_text = f"""
Original request:
{user_request}

Current extracted fields:
{json.dumps(current_data, ensure_ascii=False, indent=2)}

Missing field answers:
{json.dumps(missing_answers, ensure_ascii=False, indent=2)}
"""

        result = ask_llm(enriched_text, contexts, current_data)

        cl.user_session.set("request_data", result)
        cl.user_session.set("awaiting_missing_fields", False)
        cl.user_session.set("missing_fields", [])
        cl.user_session.set("missing_index", 0)
        cl.user_session.set("missing_answers", {})

        await cl.Message(content=render_result(result, contexts, user_request)).send()
        return

    if user_input in CUSTOMER_JOURNEYS:
        journey = CUSTOMER_JOURNEYS[user_input]
        user_request = journey["sample"]
        journey_name = journey["name"]
    else:
        user_request = user_input
        journey_name = "Custom Request"

    await cl.Message(content=f"""
## Selected Request

**Journey:** {journey_name}

**Description:**  
{user_request}
""").send()

    await cl.Message(content="🦅 Scout Agent is analyzing the request...").send()

    contexts = rag_search(user_request)
    cl.user_session.set("contexts", contexts)
    cl.user_session.set("user_request", user_request)

    await cl.Message(
        content=f"✅ RAG completed. **{len(contexts)}** relevant enterprise sources found."
    ).send()

    result = ask_llm(user_request, contexts)
    cl.user_session.set("request_data", result)

    await cl.Message(content=render_result(result, contexts, user_request)).send()

    missing = get_missing_fields(result)

    if missing:
        cl.user_session.set("awaiting_missing_fields", True)
        cl.user_session.set("missing_fields", missing)
        cl.user_session.set("missing_index", 0)
        cl.user_session.set("missing_answers", {})

        await cl.Message(content=f"""
## ⚠️ Missing Fields Detected

**{len(missing)} missing field(s)** found.

Inspector Agent will ask the missing fields one by one.  
The request maturity will be recalculated only after all answers are collected.
""").send()

        await ask_next_missing_field()
    else:
        await cl.Message(content="✅ Request is mature. No missing fields detected.").send()