"""KB ingestion and retrieval over ChromaDB with local embeddings."""
from pathlib import Path

from .config import load_settings

_model = None


def _get_model(model_name):
    """Lazily load (and cache) the sentence-transformers model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(model_name)
    return _model


def _embed(texts, model_name, embed_fn=None):
    """Embed texts; embed_fn is injectable for tests."""
    if embed_fn is not None:
        return embed_fn(texts)
    return _get_model(model_name).encode(
        texts, normalize_embeddings=True).tolist()


def _get_collection(chroma_path):
    """Open (or create) the ChromaDB collection at CHROMA_PATH."""
    import chromadb
    client = chromadb.PersistentClient(path=str(chroma_path))
    return client.get_or_create_collection(
        name="ticketpilot-kb", metadata={"hnsw:space": "cosine"})


def parse_doc(path: Path):
    """Parse one kb/*.md file into (metadata_dict, full_text)."""
    text = path.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---"):
        head, _, body = text[3:].partition("\n---")
        for line in head.strip().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
    meta.setdefault("doc_id", path.stem)
    return meta, text


def get_sections(doc_id, kb_dir=None):
    """Return {section_heading: text} for one doc, e.g. 'Steps to fix'."""
    settings = load_settings()
    kb_dir = Path(kb_dir or settings.kb_dir)
    for path in sorted(kb_dir.glob("*.md")):
        meta, text = parse_doc(path)
        if meta["doc_id"] != doc_id:
            continue
        sections, current = {}, None
        for line in text.splitlines():
            if line.startswith("## "):
                current = line[3:].strip()
                sections[current] = []
            elif current is not None:
                sections[current].append(line)
        return {k: "\n".join(v).strip() for k, v in sections.items()}
    return {}


def ingest(kb_dir=None, chroma_path=None, embedding_model=None,
           collection=None, embed_fn=None) -> int:
    """Ingest kb/*.md into ChromaDB. Safe to rerun (upsert, no duplicates)."""
    settings = load_settings()
    kb_dir = Path(kb_dir or settings.kb_dir)
    collection = collection or _get_collection(
        chroma_path or settings.chroma_path)
    model_name = embedding_model or settings.embedding_model
    docs = sorted(kb_dir.glob("*.md"))
    ids, texts, metadatas = [], [], []
    for path in docs:
        meta, text = parse_doc(path)
        ids.append(meta["doc_id"])
        texts.append(text)
        metadatas.append({"doc_id": meta["doc_id"],
                          "title": meta.get("title", ""),
                          "category": meta.get("category", ""),
                          "owner_team": meta.get("owner_team", "")})
    if ids:
        collection.upsert(ids=ids, documents=texts,
                          embeddings=_embed(texts, model_name, embed_fn),
                          metadatas=metadatas)
    return len(ids)


def retrieve(query, category=None, k=3, kb_dir=None, chroma_path=None,
             embedding_model=None, collection=None, embed_fn=None,
             min_score=None):
    """Return [{doc_id, title, score, snippet}] for docs above KB_MIN_SCORE."""
    settings = load_settings()
    min_score = settings.kb_min_score if min_score is None else min_score
    collection = collection or _get_collection(
        chroma_path or settings.chroma_path)
    if collection.count() == 0:
        return []
    model_name = embedding_model or settings.embedding_model
    where = {"category": category} if category else None
    res = collection.query(
        query_embeddings=_embed([query], model_name, embed_fn),
        n_results=min(k, collection.count()), where=where,
        include=["documents", "metadatas", "distances"])
    out = []
    for doc_id, meta, dist, document in zip(
            res["ids"][0], res["metadatas"][0], res["distances"][0],
            res["documents"][0]):
        score = 1.0 - float(dist)  # cosine distance -> similarity
        if score < min_score:
            continue
        out.append({"doc_id": meta.get("doc_id", doc_id),
                    "title": meta.get("title", ""),
                    "score": round(score, 4),
                    "snippet": " ".join(document.split())[:1500]})
    return out
