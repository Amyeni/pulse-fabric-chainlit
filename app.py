import os
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
        "sample": "Eski kampanya performans verilerini tekrar analiz etmek istiyoruz. Veri 5 yıl öncesine ait."
    },
    "3": {
        "name": "Mevcut Veriyi Bulma ve Yönlendirme",
        "sample": "Müşteri segmentasyon raporu için gerekli verinin hangi platformda olduğunu öğrenmek istiyoruz."
    }
}


def calculate_maturity(request_data):
    filled = sum(1 for field in REQUIRED_FIELDS if request_data.get(field))
    return int((filled / len(REQUIRED_FIELDS)) * 100)


def build_progress_bar(score):
    filled = int(score / 10)
    empty = 10 - filled
    return "🟩" * filled + "⬜" * empty


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


async def show_status_panel(request_data):
    score = calculate_maturity(request_data)
    progress = build_progress_bar(score)

    filled_fields = [
        field for field in REQUIRED_FIELDS
        if request_data.get(field)
    ]

    missing_fields = [
        field for field in REQUIRED_FIELDS
        if not request_data.get(field)
    ]

    await cl.Message(
        content=f"""
## 📊 Request Maturity Dashboard

**Maturity Score:** %{score}  
{progress}

**Tamamlanan Alanlar:** {len(filled_fields)} / {len(REQUIRED_FIELDS)}  
**Eksik Alanlar:** {len(missing_fields)}

**Mevcut Durum:**  
{"✅ Agent değerlendirmesine hazır" if score >= 80 else "⚠️ Talep olgunlaştırılıyor"}
"""
    ).send()


async def ask_missing_fields(request_data):
    for field, question in REQUIRED_FIELDS.items():
        if not request_data.get(field):

            await show_status_panel(request_data)

            response = await cl.AskUserMessage(
                content=f"""
### 🔎 Inspector Agent

{question}
""",
                timeout=300
            ).send()

            if response and response.get("output"):
                request_data[field] = response["output"]

    return request_data


async def run_full_agent_workflow(request_data):
    await cl.Message(
        content="""
# 🤖 Agent Workflow Başladı

Talep yeterli olgunluk seviyesine ulaştı. Şimdi dijital takım arkadaşları çalışıyor.
"""
    ).send()

    scout_output = run_agent(
        "Scout Agent",
        "Identify domain, owner, platform, request type and confidence score.",
        request_data
    )

    await cl.Message(
        content=f"""
## 🦅 Scout Agent

**Görev:** Domain, owner ve request type tespiti

{scout_output}
"""
    ).send()

    inspector_output = run_agent(
        "Inspector Agent",
        "Evaluate request maturity, missing fields, ambiguity and data quality readiness.",
        request_data
    )

    await cl.Message(
        content=f"""
## 🦉 Inspector Agent

**Görev:** Talep olgunluğu ve kalite kontrolü

{inspector_output}
"""
    ).send()

    guardian_output = run_agent(
        "Guardian Agent",
        "Evaluate PII/KVKK risk, architecture review need, required approvals and guardrail impact.",
        request_data
    )

    await cl.Message(
        content=f"""
## 🦏 Guardian Agent

**Görev:** KVKK, guardrail ve approval kontrolü

{guardian_output}
"""
    ).send()

    strategist_output = run_agent(
        "Strategist Agent",
        "Calculate priority, business impact, urgency and recommended next step.",
        request_data
    )

    await cl.Message(
        content=f"""
## 🐺 Strategist Agent

**Görev:** Öncelik, etki ve aksiyon planı

{strategist_output}
"""
    ).send()

    scribe_output = run_agent(
        "Scribe Agent",
        "Create BRD draft, scope summary, assumptions and open questions.",
        request_data
    )

    await cl.Message(
        content=f"""
## 🐙 Scribe Agent

**Görev:** BRD ve analiz taslağı

{scribe_output}
"""
    ).send()

    conductor_output = run_agent(
        "Conductor Agent",
        "Create final decision package for architecture governance board.",
        request_data
    )

    await cl.Message(
        content=f"""
# 🐬 Final Decision Package

{conductor_output}
"""
    ).send()


@cl.on_chat_start
async def start():
    cl.user_session.set("request_data", {})
	
    await cl.Message(
    content="## Digital Teammates",
    elements=[
        cl.Image(
            name="Pulse Fabric Agents",
            path="public/Demo grafik1.png",
            display="inline"
        )
    ]
    ).send()
  

    await cl.Message(
        content="""
# 🌐 Pulse Fabric MVP

**AI-powered Demand Governance & Request Maturation Demo**

Aşağıdaki agent ekibi talebi birlikte değerlendirir:

🦅 **Scout** – Domain ve talep tipini bulur  
🦉 **Inspector** – Eksik alanları ve kaliteyi kontrol eder  
🐙 **Scribe** – BRD / analiz taslağı üretir  
🐺 **Strategist** – Öncelik ve iş etkisini hesaplar  
🐬 **Conductor** – Final karar paketini oluşturur  
🦏 **Guardian** – KVKK, guardrail ve approval kontrolü yapar  

---

Lütfen bir customer journey seç:

**1** - KVKK / PII Riskli Talep  
**2** - Retention Süresi Geçmiş Veri Talebi  
**3** - Mevcut Veriyi Bulma ve Yönlendirme  

Sadece `1`, `2` veya `3` yaz.
"""
    ).send()


@cl.on_message
async def main(message: cl.Message):
    request_data = cl.user_session.get("request_data") or {}
    user_input = message.content.strip()

    if "journey" not in request_data:
        if user_input not in CUSTOMER_JOURNEYS:
            await cl.Message(
                content="Lütfen `1`, `2` veya `3` yazarak bir customer journey seç."
            ).send()
            return

        journey = CUSTOMER_JOURNEYS[user_input]
        request_data["journey"] = journey["name"]
        request_data["initial_request"] = journey["sample"]

        cl.user_session.set("request_data", request_data)

        await cl.Message(
            content=f"""
## 🎬 Seçilen Customer Journey

**{journey["name"]}**

Örnek talep:

> {journey["sample"]}

Şimdi bu talebi olgunlaştırmaya başlıyorum.
"""
        ).send()

        request_data = await ask_missing_fields(request_data)

        score = calculate_maturity(request_data)
        await show_status_panel(request_data)

        if score >= 80:
            await run_full_agent_workflow(request_data)

        cl.user_session.set("request_data", request_data)
        return

    request_data["initial_request"] = user_input

    await cl.Message(
        content="Intake Agent: Yeni talep alındı. Olgunluk kontrolü başlıyor."
    ).send()

    request_data = await ask_missing_fields(request_data)

    score = calculate_maturity(request_data)
    await show_status_panel(request_data)

    if score >= 80:
        await run_full_agent_workflow(request_data)

    cl.user_session.set("request_data", request_data)



