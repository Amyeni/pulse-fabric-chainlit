import json
import pandas as pd
from docx import Document
from pathlib import Path

DATA_DIR = Path("data")
OUTPUT_FILE = Path("rag_index.json")

chunks = []

def add_chunk(source, title, text, metadata=None):
    text = str(text).strip()
    if not text:
        return
    chunks.append({
        "source": source,
        "title": title,
        "text": text,
        "metadata": metadata or {}
    })

def load_guardrail():
    doc_path = DATA_DIR / "guardrail.docx"
    doc = Document(doc_path)

    current_section = "Guardrail Policy"
    buffer = []

    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue

        if len(txt) < 80 and not txt.endswith("."):
            if buffer:
                add_chunk("guardrail.docx", current_section, "\n".join(buffer))
                buffer = []
            current_section = txt
        else:
            buffer.append(txt)

    if buffer:
        add_chunk("guardrail.docx", current_section, "\n".join(buffer))

def load_domains():
    excel_path = DATA_DIR / "data_domains.xlsx"
    df = pd.read_excel(excel_path)

    for _, row in df.iterrows():
        domain_name = str(row.get("Domain Name", "")).strip()
        category = str(row.get("Category", "")).strip()
        definition = str(row.get("Definition (Summary)", "")).strip()
        sample_data = str(row.get("Sample Data (Summary)", "")).strip()
        owner = str(row.get("Data Owner", "")).strip()
        team = str(row.get("Related Sub-Team", "")).strip()

        text = f"""
Domain Name: {domain_name}
Category: {category}
Definition: {definition}
Sample Data: {sample_data}
Data Owner: {owner}
Related Sub-Team: {team}
""".strip()

        add_chunk(
            source="data_domains.xlsx",
            title=domain_name,
            text=text,
            metadata={
                "domain_name": domain_name,
                "category": category,
                "owner": owner,
                "team": team
            }
        )

def main():
    load_guardrail()
    load_domains()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"RAG index created: {OUTPUT_FILE}")
    print(f"Total chunks: {len(chunks)}")

if __name__ == "__main__":
    main()