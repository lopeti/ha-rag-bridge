# Home Assistant Extended OpenAI Conversation Integrációs Példa
# Használja a ha-rag-bridge-et relevancia-alapú entitás kiválasztáshoz

import jinja2
from pathlib import Path
from ha_rag_bridge import query as rag_query

# Eredeti template betöltése
TEMPLATE_PATH = Path("/app/prompt_template_optimized.txt")
TEMPLATE_STRING = TEMPLATE_PATH.read_text(encoding="utf-8")


def get_prompt_for_extended_openai_conversation(user_question, top_k=5):
    """
    Generál egy promptot az Extended OpenAI Conversation számára
    a ha-rag-bridge segítségével előválogatott releváns entitásokkal.

    Args:
        user_question: A felhasználó kérdése
        top_k: Maximális entitás szám

    Returns:
        A formázott prompt
    """
    # RAG keresés a kérdés alapján
    response = rag_query(user_question, top_k=top_k)

    # Jinja2 template előkészítése
    template = jinja2.Template(TEMPLATE_STRING)

    # Adatok előkészítése a template-hez
    context = {
        "relevant_entities": response.get("relevant_entities", []),
        "user_question": user_question,
    }

    # Template renderelése
    return template.render(**context)


# Használati példa:
# prompt = get_prompt_for_extended_openai_conversation("Milyen állapotban van a nappali lámpa?")
# print(prompt)
