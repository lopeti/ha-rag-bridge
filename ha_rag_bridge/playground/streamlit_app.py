"""Minimal Streamlit UI to poke the RAG pipeline interactively."""

from __future__ import annotations

import json

import streamlit as st

from ha_rag_bridge import query as rag_query

# --------------------------------------------------------------------------- #
#  Page config & layout
# --------------------------------------------------------------------------- #

st.set_page_config(page_title="ha-rag-bridge Playground", page_icon="🧩", layout="centered")
st.title("🧩 ha-rag-bridge Playground")
st.caption("Gyors tesztfelület a retriever + prompt finomhangolásához.")

# --------------------------------------------------------------------------- #
#  Controls
# --------------------------------------------------------------------------- #

question = st.text_area("Kérdés", "Melyik eszköz felelős a hibrid rag-bridge-ért?")
top_k = st.slider("top_k (találatok száma)", 1, 10, 3)

if st.button("Futtatás"):
    if not question.strip():
        st.warning("Adj meg egy kérdést!")
        st.stop()

    with st.spinner("Lekérdezés…"):
        response = rag_query(question, top_k=top_k)

    # ----------------------------------------------------------------------- #
    #  Results
    # ----------------------------------------------------------------------- #
    st.subheader("Válasz")
    st.write(response.get("answer", "<nincs 'answer' mező>"))

    with st.expander("ℹ️ Teljes JSON"):
        st.json(response, expanded=False)

# --------------------------------------------------------------------------- #
#  Convenience CLI entry-point
# --------------------------------------------------------------------------- #

def main() -> None:  # pragma: no cover
    """Run via `python -m ha_rag_bridge.playground.streamlit_app`."""
    import subprocess
    import sys
    subprocess.run(
        ["streamlit", "run", "-q", "-"],
        input=__file__.encode(),
        check=True,
    )


if __name__ == "__main__":  # pragma: no cover
    main()

