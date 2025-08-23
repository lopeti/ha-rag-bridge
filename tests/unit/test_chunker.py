from ha_rag_bridge.utils.chunker import split_text


def test_split_text_utf8():
    text = "ő" * 200
    chunks = list(split_text(text, width=50))
    assert "".join(chunks) == text
    # If there are no whitespace breaks, textwrap may return one large chunk.
    # The goal is only to avoid splitting inside multi-byte characters.
    assert any(len(c) >= 200 for c in chunks)
