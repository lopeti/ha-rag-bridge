# ---
# jupyter:
#   jupytext_format_version: '1.3'
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # ha-rag-bridge Playground (Notebook)
#
# Rövid, önmagában futtatható notebook a retriever & prompt vizsgálatához.
#
# * Kérdés megadása
# * `top_k` paraméter állítása
# * JSON kimenet megjelenítése

# %%
import json

from ha_rag_bridge import query

question = "Melyik eszköz felelős a hibrid rag-bridge-ért?"
response = query(question)

print(json.dumps(response, indent=2, ensure_ascii=False))

# %%
top_k = 5
response = query(question, top_k=top_k)
print(json.dumps(response, indent=2, ensure_ascii=False))

# %% [markdown]
# ## Prompt-preview
# (ha a pipeline `prompt` kulcsot is visszaad)

# %%
print(response.get("prompt", "<nincs prompt mező>"))
