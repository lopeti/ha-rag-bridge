from __future__ import annotations
import os
import argparse
from typing import List, Iterable, Tuple

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
from arango import ArangoClient

from ha_rag_bridge.logging import get_logger

from .embedding_backends import (
    BaseEmbeddingBackend as EmbeddingBackend,
    LocalBackend,
    OpenAIBackend,
    get_backend,
)

logger = get_logger(__name__)


def extract_pages_text(path: str) -> List[Tuple[int, str]]:
    pages = []
    for i, layout in enumerate(extract_pages(path), start=1):
        texts = []
        for element in layout:
            if isinstance(element, LTTextContainer):
                texts.append(element.get_text())
        pages.append((i, " ".join(texts).strip()))
    return pages


def chunk_tokens(text: str, size: int = 500, overlap: int = 50) -> Iterable[str]:
    tokens = text.split()
    step = size - overlap
    for start in range(0, len(tokens), step):
        chunk = tokens[start : start + size]
        if not chunk:
            break
        yield " ".join(chunk)
        if start + size >= len(tokens):
            break


def ingest(file: str, device_id: str) -> None:
    backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()
    if backend_name == "openai":  # keep for backward compat in tests
        emb_backend: EmbeddingBackend = OpenAIBackend()
    elif backend_name == "local":
        emb_backend = LocalBackend()
    else:
        emb_backend = get_backend(backend_name)

    arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
    db_name = os.getenv("ARANGO_DB", "_system")
    db = arango.db(
        db_name,
        username=os.environ["ARANGO_USER"],
        password=os.environ["ARANGO_PASS"],
    )
    doc_col = db.collection("document")
    edge_col = db.collection("edge")

    pages = extract_pages_text(file)
    chunks = []
    for page_num, text in pages:
        for idx, chunk in enumerate(chunk_tokens(text)):
            chunks.append((page_num, idx, chunk))

    if not chunks:
        logger.warning("no text extracted", file=file)
        return

    texts = [c[2] for c in chunks]
    embeddings = emb_backend.embed(texts)

    base_id = os.path.splitext(os.path.basename(file))[0]
    docs = []
    for (page, idx, chunk_text), emb in zip(chunks, embeddings):
        docs.append(
            {
                "_key": f"doc_{base_id}_p{page}_{idx}",
                "document_id": f"{base_id}_manual",
                "page": page,
                "chunk_idx": idx,
                "text": chunk_text,
                "embedding": emb,
            }
        )

    doc_col.insert_many(docs, overwrite=True, overwrite_mode="update")
    doc_col.insert(
        {"_key": f"{base_id}_manual"}, overwrite=True, overwrite_mode="update"
    )

    edge = {
        "_from": f"device/{device_id}",
        "_to": f"document/{base_id}_manual",
        "label": "device_has_manual",
        "source": "ingest_docs.py",
        "weight": 1.0,
    }
    edge_col.insert(edge, overwrite=True, overwrite_mode="update")

    logger.info("inserted manual chunks", chunks=len(docs), device=device_id)


def cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--device_id", required=True)
    args = parser.parse_args()
    ingest(args.file, args.device_id)


if __name__ == "__main__":
    cli()
