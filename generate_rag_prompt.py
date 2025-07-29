#!/usr/bin/env python3
"""
HA-RAG optimalizált prompt generáló script az Extended OpenAI Conversation számára.
Ez a script a ha-rag-bridge query funkcióját használja a releváns entitások
meghatározásához, majd beilleszti őket egy optimalizált promptba.
"""

import sys
import jinja2
from datetime import datetime
from pathlib import Path
from ha_rag_bridge import query as rag_query

# Alapértelmezett template elérési út - állítsd be a megfelelő útvonalra
DEFAULT_TEMPLATE_PATH = "/config/prompt_template_optimized.txt"


def now():
    """Aktuális idő visszaadása formázott stringként"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_prompt(question, template_path=None):
    """Generál egy promptot a RAG-alapú releváns entitásokkal"""
    if not template_path:
        template_path = DEFAULT_TEMPLATE_PATH

    # Ellenőrizzük, hogy létezik-e a template fájl
    if not Path(template_path).exists():
        print(f"Template file not found at {template_path}", file=sys.stderr)
        # Fallback alap template
        template_string = """I want you to act as smart home manager of Home Assistant
I will provide information of smart home along with a question, you will truthfully make correction or answer using information provided in one sentence in everyday language.

Current Time: {{now()}}

{% if relevant_entities %}
Available Devices (relevant to your query):
```csv
entity_id,name,state,aliases
{% for entity in relevant_entities %}
{{ entity.entity_id }},{{ entity.name }},{{ entity.state }},{{ entity.aliases | join('/') }}
{% endfor %}
```
{% endif %}

The current state of devices is provided in available devices.
Use execute_services function only for requested action, not for current states.
Do not execute service without user's confirmation.
Do not restate or appreciate what user says, rather make a quick inquiry."""
    else:
        template_string = Path(template_path).read_text(encoding="utf-8")

    # RAG lekérdezés futtatása
    try:
        response = rag_query(question, top_k=5)
        relevant_entities = response.get("relevant_entities", [])
    except Exception as e:
        print(f"Error during RAG query: {e}", file=sys.stderr)
        relevant_entities = []

    # Jinja2 template előkészítése
    env = jinja2.Environment()
    env.globals["now"] = now
    template = env.from_string(template_string)

    # Adatok előkészítése a template-hez
    context = {"relevant_entities": relevant_entities, "user_question": question}

    # Template renderelése
    return template.render(**context)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            'Usage: generate_rag_prompt.py "user question" [template_path]',
            file=sys.stderr,
        )
        sys.exit(1)

    user_question = sys.argv[1]
    template_path = sys.argv[2] if len(sys.argv) > 2 else None

    prompt = generate_prompt(user_question, template_path)
    print(prompt)
