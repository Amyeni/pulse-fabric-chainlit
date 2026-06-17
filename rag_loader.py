import json
import os
from docx import Document
import pandas as pd

DATA_DIR = "data"
GUARDRAIL_PATH = os.path.join(DATA_DIR, "guardrail_en.docx")
DOMAIN_PATH = os.path.join(DATA_DIR, "data_domains.xlsx")

RAG_INDEX_PATH = "rag_index.json"
DOMAIN_CATALOG_PATH = "domain_catalog.json"
GUARDRAIL_CHUNKS_PATH = "guardrail_chunks.json"


def clean_value(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def chunk_text(text, chunk_size=900):
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)

    return chunks


def load_guardrail():
    doc = Document(GUARDRAIL_PATH)

    paragraphs = [
        p.text.strip()
        for p in doc.paragraphs
        if p.text and p.text.strip()
    ]

    full_text = "\n".join(paragraphs)
    chunks = chunk_text(full_text, chunk_size=120)

    guardrail_chunks = []

    for idx, chunk in enumerate(chunks, start=1):
        guardrail_chunks.append({
            "id": f"guardrail_{idx}",
            "source": "guardrail.docx",
            "type": "guardrail",
            "text": chunk
        })

    return guardrail_chunks


def load_domain_catalog():
    df = pd.read_excel(DOMAIN_PATH)

    domain_catalog = []

    for _, row in df.iterrows():
        domain_name = clean_value(row.get("Domain Name"))
        if not domain_name:
            continue

        record = {
            "domain_no": clean_value(row.get("Domain No")),
            "domain_name": domain_name,
            "category": clean_value(row.get("Category")),
            "definition": clean_value(row.get("Definition (Summary)")),
            "sample_data": clean_value(row.get("Sample Data (Summary)")),
            "data_owner": clean_value(row.get("Data Owner")),
            "related_sub_team": clean_value(row.get("Related Sub-Team")),
        }

        domain_catalog.append(record)

    return domain_catalog


def domain_to_rag_chunk(domain):
    return {
        "id": f"domain_{domain.get('domain_no') or domain.get('domain_name')}",
        "source": "data_domains.xlsx",
        "type": "domain",
        "text": (
            f"Domain No: {domain.get('domain_no')}\n"
            f"Domain Name: {domain.get('domain_name')}\n"
            f"Category: {domain.get('category')}\n"
            f"Definition: {domain.get('definition')}\n"
            f"Sample Data: {domain.get('sample_data')}\n"
            f"Data Owner: {domain.get('data_owner')}\n"
            f"Related Sub-Team: {domain.get('related_sub_team')}"
        )
    }


def main():
    if not os.path.exists(GUARDRAIL_PATH):
        raise FileNotFoundError(f"Missing file: {GUARDRAIL_PATH}")

    if not os.path.exists(DOMAIN_PATH):
        raise FileNotFoundError(f"Missing file: {DOMAIN_PATH}")

    guardrail_chunks = load_guardrail()
    domain_catalog = load_domain_catalog()
    domain_chunks = [domain_to_rag_chunk(d) for d in domain_catalog]

    rag_index = guardrail_chunks + domain_chunks

    with open(RAG_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(rag_index, f, ensure_ascii=False, indent=2)

    with open(DOMAIN_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(domain_catalog, f, ensure_ascii=False, indent=2)

    with open(GUARDRAIL_CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(guardrail_chunks, f, ensure_ascii=False, indent=2)

    print("RAG index created:", RAG_INDEX_PATH)
    print("Domain catalog created:", DOMAIN_CATALOG_PATH)
    print("Guardrail chunks created:", GUARDRAIL_CHUNKS_PATH)
    print("Guardrail chunks:", len(guardrail_chunks))
    print("Domain records:", len(domain_catalog))
    print("Total RAG chunks:", len(rag_index))


if __name__ == "__main__":
    main()