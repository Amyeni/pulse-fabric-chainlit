import os
import json
from dotenv import load_dotenv
import chainlit as cl
from openai import OpenAI

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "flagship")
API_BASE = os.getenv("API_BASE")
API_KEY = os.getenv("API_KEY")

client = OpenAI(
    api_key=API_KEY,
    base_url=API_BASE
)

AGENT_IMAGE_PATH = "public/agents.png"

REQUIRED_FIELDS = {
    "business_need": "İş ihtiyacı nedir?",
    "data_domain": "Hangi veri domaini ile ilgili?",
    "source_system": "Kaynak sistem nedir?",
    "target_output": "Beklenen çıktı nedir?",
    "consumer": "Bu çıktıyı kim kullanacak?",
    "frequency": "Veri/rapor hangi frekansta çalışacak?",
    "pii_data": "Kişisel veri veya hassas veri içeriyor mu?",
    "deadline": "Beklenen teslim tarihi nedir?"
}

CUSTOMER_JOURNEYS = {
    "1": {
        "name": "KVKK / PII Riskli Talep",
        "sample": "Kampanya hedefleme için müşteri telefon numarası, TCKN, lokasyon ve paket bilgilerini içeren dataset istiyoruz."
    },
    "2": {
        "name": "Retention Süresi Geçmiş Veri Talebi",
        "sample": "5 yıl öncesine ait kampanya performans verilerini tekrar analiz etmek istiyoruz."
    },
    "3": {
        "name": "Mevcut Veriyi Bulma ve Yönlendirme",
        "sample": "Müşteri segmentasyon raporu için gerekli verinin hangi platformda olduğunu öğrenmek istiyoruz."
    }
}


def safe_json_loads(text):
    try:
        text = text.strip()
        text = text.replace("```json", "").replace("```", "")
        return json.loads(text)
    except Exception:
        return {}


def calculate_maturity(data):
    filled = sum(1 for field in REQUIRED_FIELDS if data.get(field))
    return int((filled / len(REQUIRED_FIELDS)) * 100)


def get_missing_fields(data):
    return [field for field in REQUIRED_FIELDS if not data.get(field)]


def extract_fields_with_llm(user_text, current_data):
    prompt = f"""
You are Pulse Fabric Request Maturation Agent.

Your task is to extract and update structured request fields from the user's message.

Current request data:
{current_data}

User message:
{user_text}

Fields to extract:
- business_need
- data_domain
- source_system
- target_output
- consumer
- frequency
- pii_data
- deadline

Also infer:
- domain
- request_type
- risk_level
- priority
- priority_score
- guardian_decision
- next_step

Rules:
- Do not overwrite existing non-empty fields unless user clearly corrects them.
- If a field is unknown, return empty string.
- If the message contains TCKN, MSISDN, phone number, location, identity number, customer level data, mark pii_data as Yes.
- If PII exists, risk_level should be HIGH and guardian_decision should be Human Approval Required.
- Return ONLY valid JSON.
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "Return only valid JSON. No markdown."},
            {"role": "user", "content": prompt}
        ]
    )

    extracted = safe_json_loads(response.choices[0].message.content)

    merged = current_data.copy()

    for key, value in extracted.items():
        if value not in [None, "", "unknown", "Unknown", "N/A"]:
            if not merged.get(key) or key not in REQUIRED_FIELDS:
                merged[key] = value

    return merged


def llm_json_analysis(request_data):
    prompt = f"""
You are Pulse Fabric AI Governance Engine.

Analyze this request and return ONLY valid JSON.

Request data:
{request_data}

Return JSON with:
domain, request_type, priority_score, priority, risk_level, guardian_decision, next_step
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "Return only valid JSON. No markdown."},
            {"role": "user", "content": prompt}
        ]
    )

    parsed = safe_json_loads(response.choices[0].message.content)

    if not parsed:
        parsed = {
            "domain": request_data.get("data_domain", "Customer Analytics"),
            "request_type": "Sensitive Data Access" if request_data.get("pii_data", "").lower() in ["yes", "evet"] else "Standard Data Request",
            "priority_score": 90,
            "priority": "P1 - High Priority",
            "risk_level": "HIGH" if request_data.get("pii_data", "").lower() in ["yes", "evet"] else "MEDIUM",
            "guardian_decision": "Human Approval Required" if request_data.get("pii_data", "").lower() in ["yes", "evet"] else "Conditional Pass",
            "next_step": "Route to human approval" if request_data.get("pii_data", "").lower() in ["yes", "evet"] else "Proceed with architecture review"
        }

    return parsed


def run_agent(agent_name, task, request_data):
    prompt = f"""
You are {agent_name} in Pulse Fabric.

Task:
{task}

Request Data:
{request_data}

Return in Turkish.
Use concise enterprise language.
Use bullet points.
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are an enterprise AI governance agent."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content


def dashboard_html(request_data, analysis):
    score = calculate_maturity(request_data)
    missing = get_missing_fields(request_data)

    return f"""




"""


async def show_dashboard(request_data):
    analysis = llm_json_analysis(request_data)
    cl.user_session.set("analysis", analysis)

    await cl.Message(
        content=dashboard_html(request_data, analysis)
    ).send()


async def ask_next_missing_field(request_data):
    missing = get_missing_fields(request_data)

    if not missing:
        return request_data, False

    next_field = missing[0]
    question = REQUIRED_FIELDS[next_field]

    await show_dashboard(request_data)

    response = await cl.AskUserMessage(
        content=f"### 🔎 Inspector Agent\n{question}",
        timeout=300
    ).send()

    if response and response.get("output"):
        user_answer = response["output"]

        enriched_data = extract_fields_with_llm(
            user_answer,
            request_data
        )

        request_data.update(enriched_data)

    cl.user_session.set("request_data", request_data)
    return request_data, True


async def mature_request_loop(request_data):
    while True:
        missing = get_missing_fields(request_data)

        if not missing:
            break

        previous_missing_count = len(missing)

        request_data, asked = await ask_next_missing_field(request_data)

        new_missing_count = len(get_missing_fields(request_data))

        if not asked:
            break

        if new_missing_count == previous_missing_count:
            continue

    return request_data


async def final_workflow(request_data):
    analysis = cl.user_session.get("analysis") or llm_json_analysis(request_data)

    guardian = run_agent(
        "Guardian Agent",
        "Evaluate KVKK/PII risk, architecture review need and required approvals.",
        request_data
    )

    scribe = run_agent(
        "Scribe Agent",
        "Create BRD draft, assumptions, scope summary and open questions.",
        request_data
    )

    conductor = run_agent(
        "Conductor Agent",
        "Create final decision package for governance board.",
        request_data
    )

    await cl.Message(
        content=f"""

### Guardian Output
{guardian}

---

### Generated Documentation - Scribe
{scribe}

---

# Final Decision Package
{conductor}

---

## Human in the Loop

✅ Approve &nbsp;&nbsp;&nbsp; 🔁 Send Back &nbsp;&nbsp;&nbsp; ❌ Reject
"""
    ).send()


@cl.on_chat_start
async def start():
    cl.user_session.set("request_data", {})

    if os.path.exists(AGENT_IMAGE_PATH):
        await cl.Message(
            content="## Pulse Fabric Digital Teammates",
            elements=[
                cl.Image(
                    name="Pulse Fabric Agents",
                    path=AGENT_IMAGE_PATH,
                    display="inline"
                )
            ]
        ).send()

    await cl.Message(
        content="""



"""
    ).send()


@cl.on_message
async def main(message: cl.Message):
    request_data = cl.user_session.get("request_data") or {}
    user_input = message.content.strip()

    if "journey" not in request_data:
        if user_input not in CUSTOMER_JOURNEYS:
            await cl.Message(content="Lütfen sadece `1`, `2` veya `3` yaz.").send()
            return

        journey = CUSTOMER_JOURNEYS[user_input]

        request_data["journey"] = journey["name"]
        request_data["initial_request"] = journey["sample"]

        request_data = extract_fields_with_llm(
            journey["sample"],
            request_data
        )

        cl.user_session.set("request_data", request_data)

        request_data = await mature_request_loop(request_data)

        await show_dashboard(request_data)
        await final_workflow(request_data)
        return

    request_data = extract_fields_with_llm(
        user_input,
        request_data
    )

    cl.user_session.set("request_data", request_data)

    request_data = await mature_request_loop(request_data)

    await show_dashboard(request_data)
    await final_workflow(request_data)
